"""Figma API integration service.

Provides Figma REST API access for fetching file data via personal access
token or direct API calls, and a design-to-prompt converter that feeds into
the existing AI generation pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FIGMA_API_URL = "https://api.figma.com/v1"

# Max retries for Figma API 429 responses
_FIGMA_MAX_RETRIES = 3


def _parse_retry_after(response: httpx.Response, default: int = 10) -> int:
    """Parse the Retry-After header from a 429 response.

    Handles both integer seconds and HTTP-date formats per RFC 7231.
    Falls back to the response body, then to ``default``.
    Capped at 120 seconds to avoid bogus values.
    """
    header = response.headers.get("Retry-After")
    if header:
        try:
            return min(int(header), 120)
        except ValueError:
            pass
        try:
            parsed = datetime.strptime(header, "%a, %d %b %Y %H:%M:%S %Z")
            now = datetime.now(timezone.utc)
            wait = (parsed.replace(tzinfo=timezone.utc) - now).total_seconds()
            if wait > 0:
                return min(int(wait), 120)
        except ValueError:
            pass
    try:
        body = response.json()
        val = body.get("retry_after", body.get("Retry-After", default))
        return min(int(val), 120)
    except Exception:
        return default


class FigmaApiError(RuntimeError):
    """Raised when a Figma API call fails with a non-429 error."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        super().__init__(detail)


class FigmaRateLimitError(RuntimeError):
    """Raised when Figma API returns 429 and retries are exhausted.

    Attributes:
        retry_after: Seconds the caller should wait before retrying.
    """

    def __init__(self, retry_after: int, message: str | None = None) -> None:
        self.retry_after = retry_after
        if message is None:
            message = f"Figma API rate limited. Retry after {retry_after}s."
        super().__init__(message)


class FigmaService:
    """Handles Figma API interactions for design import.

    This is a stateless service — no OAuth tokens are stored. Authentication
    is done via personal access tokens passed directly to each API call.
    """

    # ── Figma API calls ───────────────────────────────────────

    async def request_with_retry(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> httpx.Response:
        """Make a Figma API request with 429 retry logic.

        Retries up to ``_FIGMA_MAX_RETRIES`` times on 429, respecting
        the ``Retry-After`` header. Raises ``FigmaRateLimitError`` if
        retries are exhausted, or ``FigmaApiError`` for other HTTP errors.
        """
        for attempt in range(_FIGMA_MAX_RETRIES + 1):
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method, url, headers=headers)

            if response.status_code == 429:
                wait = _parse_retry_after(response)
                if attempt >= _FIGMA_MAX_RETRIES:
                    raise FigmaRateLimitError(
                        retry_after=wait,
                        message=f"Figma API rate limited (429). Retry after {wait}s. Max retries ({_FIGMA_MAX_RETRIES}) exceeded.",
                    )
                logger.warning("Figma API rate limited (429). Retrying in %ds (attempt %d/%d)", wait, attempt + 1, _FIGMA_MAX_RETRIES)
                await asyncio.sleep(wait)
                continue

            if not response.is_success:
                raise FigmaApiError(
                    status=response.status_code,
                    detail=f"Figma API returned {response.status_code}: {response.text[:500]}",
                )

            return response

        # Should not be reached
        raise FigmaRateLimitError(retry_after=60)

    # ── URL parsing ──────────────────────────────────────────

    @staticmethod
    def extract_file_key(figma_url: str) -> str:
        """Extract the Figma file key from a URL or return the input if it's already a bare key.

        Handles formats:
        - ``https://www.figma.com/file/ABC123/My-Design``
        - ``https://www.figma.com/design/ABC123/My-Design``
        - ``https://www.figma.com/file/ABC123/``
        - ``ABC123`` (bare key)

        Raises ValueError if the URL can't be parsed and doesn't look like a bare key.
        """
        figma_url = figma_url.strip().rstrip("/")

        # Match both /file/KEY and /design/KEY patterns
        match = re.search(r"/file/([^/?#]+)", figma_url)
        if not match:
            match = re.search(r"/design/([^/?#]+)", figma_url)
        if match:
            return match.group(1)

        # If no URL pattern matched, assume it's a bare key
        # Figma keys are typically 12-22 alphanumeric chars
        if re.match(r"^[A-Za-z0-9_-]+$", figma_url):
            return figma_url

        raise ValueError(
            f"Could not extract a valid Figma file key from: {figma_url}. "
            "Expected a URL like https://www.figma.com/file/KEY/name or a bare file key."
        )

    # ── Color conversion helpers ────────────────────────────────

    @staticmethod
    def _rgb_to_hex(r: float, g: float, b: float) -> str:
        """Convert 0-1 RGB floats to hex string."""
        return f"#{int(round(r * 255)):02x}{int(round(g * 255)):02x}{int(round(b * 255)):02x}"

    @staticmethod
    def _get_solid_color(fills: list[dict] | None) -> str | None:
        """Extract the first solid fill color as hex, or None."""
        if not fills:
            return None
        for f in fills:
            if f.get("type") == "SOLID":
                c = f.get("color", {})
                return FigmaService._rgb_to_hex(c.get("r", 0), c.get("g", 0), c.get("b", 0))
        return None

    @staticmethod
    def _get_text_color(node: dict) -> str:
        """Extract text color from a node's fills."""
        color = FigmaService._get_solid_color(node.get("fills"))
        return color or "#000000"

    # ── Node tree walker for compact summary ────────────────────

    @staticmethod
    def _walk_nodes(
        node: dict,
        depth: int = 0,
        parent_x: float = 0,
        parent_y: float = 0,
    ) -> list[str]:
        """Walk a Figma node tree and produce compact summary lines.

        Each line describes one node with its type, name, relative position,
        dimensions, color, and text content. This summary is easier for the
        AI to parse than raw JSON, especially for background shapes and
        decorative elements that the AI tends to skip.
        """
        lines: list[str] = []
        indent = "  " * depth
        node_type = node.get("type", "UNKNOWN")
        node_name = node.get("name", "")
        bbox = node.get("absoluteBoundingBox") or {}

        x = bbox.get("x", 0)
        y = bbox.get("y", 0)
        w = bbox.get("width", 0)
        h = bbox.get("height", 0)

        # Compute position relative to parent
        rel_x = x - parent_x
        rel_y = y - parent_y

        # Get colors
        bg_color = FigmaService._get_solid_color(node.get("fills"))
        text_color = FigmaService._get_text_color(node)

        # Get text content
        characters = node.get("characters", "")
        style = node.get("style", {}) or {}

        # Get corner radius
        corner_radius = node.get("cornerRadius", 0)

        # Get stroke info
        strokes = node.get("strokes", [])
        stroke_weight = node.get("strokeWeight", 0)
        stroke_color = None
        if strokes:
            stroke_color = FigmaService._get_solid_color(strokes)

        # Get effects
        effects = node.get("effects", [])

        # Build the line
        parts = [f"{indent}[{node_type}]"]
        if node_name:
            parts.append(f'"{node_name}"')
        parts.append(f"@({rel_x:.0f},{rel_y:.0f}) {w:.0f}x{h:.0f}")

        if bg_color:
            parts.append(f"bg:{bg_color}")
        if corner_radius:
            parts.append(f"br:{corner_radius:.0f}")
        if stroke_color and stroke_weight:
            parts.append(f"bd:{stroke_weight:.0f}px {stroke_color}")
        if effects:
            for e in effects:
                if e.get("type") == "DROP_SHADOW":
                    offset = e.get("offset", {})
                    radius = e.get("radius", 0)
                    sc = e.get("color", {})
                    sh_color = FigmaService._rgb_to_hex(sc.get("r", 0), sc.get("g", 0), sc.get("b", 0))
                    parts.append(f"shadow:{offset.get('x', 0):.0f}px {offset.get('y', 0):.0f}px {radius:.0f}px {sh_color}")

        if characters:
            text_preview = characters[:80].replace("\n", "\\n")
            font_family = style.get("fontFamily", "")
            font_size = style.get("fontSize", "")
            font_weight = style.get("fontWeight", "")
            text_align = style.get("textAlignHorizontal", "")
            line_height = style.get("lineHeightPx", "")
            parts.append(f'text:"{text_preview}"')
            if font_family:
                parts.append(f"ff:{font_family}")
            if font_size:
                parts.append(f"fs:{font_size}")
            if font_weight:
                parts.append(f"fw:{font_weight}")
            if text_align and text_align != "LEFT":
                parts.append(f"ta:{text_align}")
            if line_height:
                parts.append(f"lh:{line_height:.0f}")
            if text_color:
                parts.append(f"co:{text_color}")

        # Handle gradient fills
        if bg_color is None and node.get("fills"):
            for f in node.get("fills", []):
                if f.get("type") == "GRADIENT":
                    stops = f.get("gradientStops", [])
                    if len(stops) >= 2:
                        c1 = stops[0].get("color", {})
                        c2 = stops[-1].get("color", {})
                        hex1 = FigmaService._rgb_to_hex(c1.get("r", 0), c1.get("g", 0), c1.get("b", 0))
                        hex2 = FigmaService._rgb_to_hex(c2.get("r", 0), c2.get("g", 0), c2.get("b", 0))
                        gtype = f.get("gradientType", "LINEAR")
                        parts.append(f"gradient:{gtype} {hex1}->{hex2}")

        lines.append(" ".join(parts))

        # Recurse into children
        children = node.get("children", [])
        if children:
            for child in children:
                child_lines = FigmaService._walk_nodes(child, depth + 1, x, y)
                lines.extend(child_lines)

        return lines

    # ── Design prompt builder ─────────────────────────────────

    _RAW_JSON_MAX_CHARS = 500_000  # well within 1M context window

    def build_design_prompt(
        self,
        file_data: dict[str, Any],
    ) -> str:
        """Build a prompt with a compact tree summary + raw Figma JSON.

        The prompt has three parts:
        1. A compact tree summary with pre-computed relative positions and
           CSS-ready hex colors — easy for the AI to parse at a glance.
        2. The raw Figma JSON (capped at 500k chars) for full detail.
        3. Instructions for the AI.

        The compact summary helps the AI quickly understand the structure
        and colors without having to parse raw Figma JSON. The raw JSON
        provides the full detail for pixel-perfect rendering.
        """
        document = file_data.get("document")
        if not document or not isinstance(document, dict):
            return (
                "Convert this Figma design to HTML/CSS code. "
                "The design data could not be fully parsed, so create a "
                "beautiful, responsive web page based on the design name: "
                f"{file_data.get('name', 'Untitled Design')}."
            )

        name = file_data.get("name", "Untitled Design")
        last_modified = file_data.get("lastModified", "")

        lines: list[str] = []
        lines.append(f"# Figma Design: {name}")
        if last_modified:
            lines.append(f"Last modified: {last_modified}")
        lines.append("")

        # ── Part 1: Compact tree summary ────────────────────────

        lines.append("## Design Tree Summary")
        lines.append("")
        lines.append(
            "Each line shows: [TYPE] \"name\" @(x,y) widthxheight "
            "bg:color br:radius bd:stroke shadow:offset color:text-properties"
        )
        lines.append("")

        # Walk the document tree
        tree_lines = FigmaService._walk_nodes(document)
        lines.extend(tree_lines)
        lines.append("")

        # ── Part 2: Raw Figma JSON ──────────────────────────────

        lines.append("## Full Figma JSON (for reference)")
        lines.append("")

        raw_json = json.dumps(file_data, indent=2, ensure_ascii=False)

        if len(raw_json) > self._RAW_JSON_MAX_CHARS:
            logger.warning(
                "Figma JSON is %d chars, truncating to %d",
                len(raw_json), self._RAW_JSON_MAX_CHARS,
            )
            raw_json = raw_json[:self._RAW_JSON_MAX_CHARS] + "\n  // ... [JSON truncated]"

        lines.append("```json")
        lines.append(raw_json)
        lines.append("```")
        lines.append("")

        # ── Part 3: Instructions ────────────────────────────────

        lines.append(
            "## Instructions\n"
            "\n"
            "The Design Tree Summary above shows every node with its type, position, "
            "size, colors, and text. Use it as your PRIMARY reference for generating code.\n"
            "\n"
            "The Full Figma JSON below provides the complete detail for any node that "
            "needs more information (gradient stops, exact shadow parameters, etc.).\n"
            "\n"
            "### CRITICAL: Render ALL nodes\n"
            "\n"
            "- Every [RECTANGLE] node is a background or decorative element — render it as a <div>.\n"
            "- Every [ELLIPSE] node is a circle — render it as a <div> with border-radius:50%.\n"
            "- Every [VECTOR] node is an icon — render it as a small colored <div> or inline SVG.\n"
            "- Every [GROUP] node is a container — render it as a <div> (it positions children).\n"
            "- Every [TEXT] node is text — render it with the exact font, size, weight, color.\n"
            "- Every [FRAME] node is a section/container — render it as a <div>.\n"
            "- Do NOT skip any node. Every element in the summary must appear in your HTML.\n"
            "\n"
            "### Positioning\n"
            "\n"
            "- The @(x,y) values are positions RELATIVE to the parent node.\n"
            "- Use CSS `position: absolute; left: Xpx; top: Ypx` for each element.\n"
            "- The top-level FRAME is the main container — use `position: relative`.\n"
            "\n"
            "### Colors\n"
            "\n"
            "- Colors are in CSS-ready hex format (e.g. #ff0000). Use them directly.\n"
            "- Gradients are shown as `gradient:LINEAR #color1->#color2`.\n"
            "- Shadows are shown as `shadow:offsetX offsetY blur color`.\n"
            "\n"
            "### Typography\n"
            "\n"
            "- Use the exact font family, size, weight, line height, and color shown.\n"
            "- Import Google Fonts via @import or <link> if needed.\n"
            "\n"
            "### Output rules\n"
            "\n"
            "1. Create index.html, style.css, and script.js\n"
            "2. index.html links style.css and script.js\n"
            "3. Use EXACT colors, EXACT fonts, EXACT dimensions from the summary\n"
            "4. Use CSS position:absolute with left/top for all positioned elements\n"
            "5. Use CSS flexbox for FRAME nodes with layoutMode (HORIZONTAL/VERTICAL)\n"
            "6. Match border-radius, border, opacity, and effects exactly\n"
            "7. Preserve the full node hierarchy — every node becomes an HTML element\n"
            "8. Do NOT add, remove, or rearrange elements\n"
            "9. Page must look IDENTICAL to the Figma design"
        )

        return "\n".join(lines)
