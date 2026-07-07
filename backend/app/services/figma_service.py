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

    # ── Design prompt builder ─────────────────────────────────

    _RAW_JSON_MAX_CHARS = 500_000  # well within 1M context window

    def build_design_prompt(
        self,
        file_data: dict[str, Any],
    ) -> str:
        """Build a prompt that includes the raw Figma JSON for the AI to parse.

        With a 1M context window, the AI can parse the full Figma node tree
        directly — no need for a lossy text-based spec. The raw JSON preserves
        all spatial relationships, fill/stroke properties, text styles, auto-layout
        constraints, and the full node hierarchy.

        The prompt includes:
        1. A brief design summary (name, dimensions, key metadata)
        2. The raw Figma JSON (capped at 500k chars)
        3. Instructions for the AI to interpret the JSON and generate code
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
        thumbnail_url = file_data.get("thumbnailUrl", "")

        # ── Build a compact summary header ────────────────────

        lines: list[str] = []
        lines.append(f"# Figma Design: {name}")
        if last_modified:
            lines.append(f"Last modified: {last_modified}")
        lines.append("")

        # ── Serialize the raw Figma JSON ──────────────────────

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

        # ── Instructions for the AI ───────────────────────────

        lines.append(
            "## Instructions\n"
            "\n"
            "The JSON above is the full Figma document tree for this design. "
            "Parse it and generate pixel-perfect HTML/CSS/JS code.\n"
            "\n"
            "### How to read the Figma JSON\n"
            "\n"
            "- The root is a DOCUMENT node containing CANVAS nodes (pages).\n"
            "- Each CANVAS contains FRAME nodes — these are your top-level sections/pages.\n"
            "- FRAME nodes can contain nested FRAMEs, TEXT nodes, RECTANGLE nodes, "
            "ELLIPSE nodes, LINE nodes, VECTOR nodes, GROUP nodes, and COMPONENT nodes.\n"
            "- INSTANCE nodes are component instances — treat them like their source component.\n"
            "\n"
            "### Key properties per node\n"
            "\n"
            "- `type`: FRAME, TEXT, RECTANGLE, ELLIPSE, LINE, VECTOR, GROUP, COMPONENT, INSTANCE\n"
            "- `name`: The layer name in Figma\n"
            "- `absoluteBoundingBox`: `{x, y, width, height}` — position and size in pixels\n"
            "- `fills[]`: Array of fill objects. Each has `type` (SOLID, GRADIENT, IMAGE, etc.) "
            "and `color` `{r, g, b}` (0-1 range) and `opacity` (0-1).\n"
            "- `strokes[]`: Array of stroke objects (same structure as fills). "
            "`strokeWeight` gives the width.\n"
            "- `cornerRadius`: Border radius in pixels (or `individualCornerRadius` for per-corner).\n"
            "- `effects[]`: Array of effect objects (drop shadows, inner shadows, blurs).\n"
            "- `opacity`: Node opacity (0-1).\n"
            "- `blendMode`: Blend mode (e.g. \"PASS_THROUGH\", \"MULTIPLY\").\n"
            "- `isMask`: Boolean — if true, this node is a mask.\n"
            "\n"
            "### Text nodes (type: TEXT)\n"
            "\n"
            "- `characters`: The text content\n"
            "- `style`: Object with `fontFamily`, `fontPostScriptName`, `fontSize`, `fontWeight`, "
            "`textAlignHorizontal` (LEFT, CENTER, RIGHT), `textAlignVertical` (TOP, CENTER, BOTTOM), "
            "`lineHeightPx`, `letterSpacing`, `paragraphSpacing`, `paragraphIndent`\n"
            "- `fills[0].color`: Text color\n"
            "\n"
            "### Auto-layout (FRAME nodes with layoutMode)\n"
            "\n"
            "- `layoutMode`: \"NONE\" (no auto-layout), \"HORIZONTAL\" (flex row), \"VERTICAL\" (flex column)\n"
            "- `primaryAxisAlignItems`: \"MIN\" (flex-start), \"CENTER\", \"MAX\" (flex-end), \"SPACE_BETWEEN\"\n"
            "- `counterAxisAlignItems`: \"MIN\", \"CENTER\", \"MAX\"\n"
            "- `itemSpacing`: Gap between children in pixels\n"
            "- `paddingLeft`, `paddingRight`, `paddingTop`, `paddingBottom`: Padding in pixels\n"
            "- `layoutWrap`: \"NO_WRAP\" or \"WRAP\"\n"
            "- `itemReverseZIndex`: Boolean — if true, children are rendered in reverse order\n"
            "\n"
            "### Constraints\n"
            "\n"
            "- `constraints`: `{horizontal: \"MIN\"|\"CENTER\"|\"MAX\"|\"STRETCH\"|\"SCALE\", "
            "vertical: \"MIN\"|\"CENTER\"|\"MAX\"|\"STRETCH\"|\"SCALE\"}`\n"
            "- Use constraints to determine how elements should behave on resize.\n"
            "\n"
            "### Gradients\n"
            "\n"
            "- Fills with type \"GRADIENT\" have `gradientType` (LINEAR, RADIAL, ANGULAR, DIAMOND) "
            "and `gradientStops[]` each with `position` (0-1) and `color`.\n"
            "\n"
            "### Images\n"
            "\n"
            "- Fills with type \"IMAGE\" have `imageRef` and `scaleMode` (FILL, FIT, CROP, TILE).\n"
            "- Use a colored div or inline SVG placeholder. Do NOT use external image URLs.\n"
            "\n"
            "### Output rules\n"
            "\n"
            "1. Create index.html, style.css, and script.js\n"
            "2. index.html links style.css and script.js\n"
            "3. Use EXACT colors (convert 0-1 RGB to 0-255), EXACT fonts, EXACT dimensions\n"
            "4. Use CSS position:absolute with left/top for non-auto-layout elements\n"
            "5. Use CSS flexbox for auto-layout frames (flex-direction based on layoutMode)\n"
            "6. Match border-radius, border, opacity, and effects exactly\n"
            "7. Preserve the full node hierarchy — nested frames become nested HTML elements\n"
            "8. Do NOT add, remove, or rearrange elements\n"
            "9. Page must look IDENTICAL to the Figma design"
        )

        return "\n".join(lines)
