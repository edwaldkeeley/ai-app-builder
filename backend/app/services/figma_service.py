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

    def build_design_prompt(
        self,
        file_data: dict[str, Any],
    ) -> str:
        """Extract key design information from Figma JSON and build a structured prompt.

        Produces a compact structured spec: design name, color palette, font palette,
        and a flat list of visual sections with their CSS properties. Keeps it under
        30k chars to reliably fit within AI context windows.
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

        # ── Helpers ────────────────────────────────────────────

        def _fmt_color(color: dict[str, float] | None, opacity: float | None = None) -> str:
            if not color:
                return ""
            r = round(color.get("r", 0) * 255)
            g = round(color.get("g", 0) * 255)
            b = round(color.get("b", 0) * 255)
            a = opacity if opacity is not None else color.get("a", 1.0)
            return f"rgba({r},{g},{b},{a})" if a < 1.0 else f"rgb({r},{g},{b})"

        def _get_fill(node: dict[str, Any]) -> str:
            fills = node.get("fills", [])
            if isinstance(fills, list):
                for fill in fills:
                    if isinstance(fill, dict) and fill.get("type") == "SOLID":
                        c = _fmt_color(fill.get("color"), fill.get("opacity"))
                        if c:
                            return c
            return ""

        def _get_text_info(node: dict[str, Any]) -> dict | None:
            if node.get("type") != "TEXT":
                return None
            style = node.get("style", {}) or {}
            chars = node.get("characters", "")
            if len(chars) > 100:
                chars = chars[:100] + "..."
            info: dict[str, Any] = {"text": chars}
            if style.get("fontFamily"):
                info["font"] = style["fontFamily"]
            if style.get("fontSize"):
                info["size"] = style["fontSize"]
            if style.get("fontWeight"):
                info["weight"] = style["fontWeight"]
            if style.get("textAlignHorizontal") and style["textAlignHorizontal"] != "LEFT":
                info["align"] = style["textAlignHorizontal"].lower()
            fill = _get_fill(node)
            if fill:
                info["color"] = fill
            return info

        # ── Collect top-level frames ──────────────────────────

        def _get_top_frames(node: dict) -> list[dict]:
            if node.get("type") == "DOCUMENT":
                for c in (node.get("children") or []):
                    result = _get_top_frames(c)
                    if result:
                        return result
                return []
            if node.get("type") == "CANVAS":
                return node.get("children") or []
            return []

        top_frames = _get_top_frames(document)

        # ── Extract colors and fonts ──────────────────────────

        colors: set[str] = set()
        fonts: list[dict[str, Any]] = []
        seen_fonts: set[str] = set()

        def _scan(items: list[dict]) -> None:
            for item in items:
                if not isinstance(item, dict):
                    continue
                bg = _get_fill(item)
                if bg:
                    colors.add(bg)
                text = _get_text_info(item)
                if text:
                    if "color" in text:
                        colors.add(text["color"])
                    ff = text.get("font")
                    if ff and ff not in seen_fonts:
                        seen_fonts.add(ff)
                        entry: dict[str, Any] = {"font": ff}
                        if text.get("size"):
                            entry["size"] = text["size"]
                        if text.get("weight"):
                            entry["weight"] = text["weight"]
                        fonts.append(entry)
                for c in (item.get("children") or []):
                    _scan([c])

        _scan(top_frames)

        # ── Build compact section descriptions ────────────────

        lines: list[str] = []
        lines.append(f"Design: {name}")
        lines.append("")

        if colors:
            sorted_c = sorted(colors)
            lines.append("Colors:")
            for c in sorted_c[:15]:
                lines.append(f"  {c}")
            lines.append("")

        if fonts:
            lines.append("Fonts:")
            for f in fonts[:8]:
                parts = [f["font"]]
                if f.get("size"):
                    parts.append(str(f["size"]))
                if f.get("weight"):
                    parts.append(str(f["weight"]))
                lines.append("  " + " | ".join(parts))
            lines.append("")

        lines.append("Sections:")

        # Track total output size to avoid exceeding context window
        MAX_OUTPUT_CHARS = 25000
        estimated = len("\n".join(lines))

        for fi, frame in enumerate(top_frames):
            if estimated > MAX_OUTPUT_CHARS:
                lines.append(f"  ... ({len(top_frames) - fi} more sections omitted)")
                break

            fname = frame.get("name", f"section-{fi}")
            bbox = frame.get("absoluteBoundingBox") or {}
            fw = bbox.get("width")
            fh = bbox.get("height")
            dims = f" [{round(fw,1)}x{round(fh,1)}px]" if fw and fh else ""

            bg = _get_fill(frame)
            bg_str = f" bg:{bg}" if bg else ""

            lm = frame.get("layoutMode")
            layout_str = ""
            if lm:
                direction = "row" if lm == "HORIZONTAL" else "column"
                layout_str = f" flex:{direction}"
                pa = frame.get("primaryAxisAlignItems")
                ca = frame.get("counterAxisAlignItems")
                if pa:
                    layout_str += f" justify:{pa.lower()}"
                if ca:
                    layout_str += f" align:{ca.lower()}"
                gap = frame.get("itemSpacing")
                if gap:
                    layout_str += f" gap:{round(gap,1)}px"

            cr = frame.get("cornerRadius")
            radius_str = f" radius:{round(cr,1)}px" if cr and cr > 0 else ""

            lines.append(f"  [{fi}] {fname}{dims}{bg_str}{layout_str}{radius_str}")
            estimated += len(lines[-1])

            # Direct children (one level deep, no recursion)
            children = frame.get("children") or []
            for ci, child in enumerate(children):
                if estimated > MAX_OUTPUT_CHARS:
                    break
                if not isinstance(child, dict):
                    continue

                cname = child.get("name", f"child-{ci}")
                cbbox = child.get("absoluteBoundingBox") or {}
                cw = cbbox.get("width")
                ch = cbbox.get("height")
                cdims = f" [{round(cw,1)}x{round(ch,1)}px]" if cw and ch else ""

                cbg = _get_fill(child)
                cbg_str = f" bg:{cbg}" if cbg else ""

                text = _get_text_info(child)
                text_str = ""
                if text:
                    t = text.get("text", "")
                    text_str = f" text:\"{t}\""
                    if text.get("font"):
                        text_str += f" font:{text['font']}"
                    if text.get("size"):
                        text_str += f" {text['size']}px"
                    if text.get("color"):
                        text_str += f" color:{text['color']}"

                clm = child.get("layoutMode")
                clayout_str = ""
                if clm:
                    cdir = "row" if clm == "HORIZONTAL" else "column"
                    clayout_str = f" flex:{cdir}"

                ccr = child.get("cornerRadius")
                cradius_str = f" radius:{round(ccr,1)}px" if ccr and ccr > 0 else ""

                line = f"    - {cname}{cdims}{cbg_str}{text_str}{clayout_str}{cradius_str}"
                lines.append(line)
                estimated += len(line)

        lines.append("")
        lines.append(
            "Rules:\n"
            "- Create index.html, style.css, script.js\n"
            "- index.html links style.css and script.js\n"
            "- Use the EXACT colors from the Colors list above\n"
            "- Use the EXACT fonts from the Fonts list above\n"
            "- Each [N] section is a top-level HTML section element\n"
            "- Indented children with '-' are nested inside their parent\n"
            "- Use flexbox with exact direction, justify, align, gap\n"
            "- Match border-radius and dimensions exactly\n"
            "- Do NOT add, remove, or rearrange elements\n"
            "- Use colored divs or inline SVG for images (no external URLs)\n"
            "- Page must look IDENTICAL to the Figma design"
        )

        return "\n".join(lines)
