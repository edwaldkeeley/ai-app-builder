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

        Key improvements over the previous version:
        - Includes x/y position data for every element
        - Filters to only the largest/primary frames (desktop-first)
        - Detects image fills and marks them as placeholders
        - Captures auto-layout properties more reliably
        - Provides explicit positioning instructions
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
            """Get the SOLID fill color of a node, or empty string if none."""
            fills = node.get("fills", [])
            if isinstance(fills, list):
                for fill in fills:
                    if isinstance(fill, dict) and fill.get("type") == "SOLID":
                        c = _fmt_color(fill.get("color"), fill.get("opacity"))
                        if c:
                            return c
            return ""

        def _has_image_fill(node: dict[str, Any]) -> bool:
            """Check if a node has an image fill (not a solid color)."""
            fills = node.get("fills", [])
            if isinstance(fills, list):
                for fill in fills:
                    if isinstance(fill, dict) and fill.get("type") in ("IMAGE", "EMOJI_TILED"):
                        return True
            return False

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
            if style.get("lineHeightPx"):
                info["lineHeight"] = style["lineHeightPx"]
            if style.get("letterSpacing"):
                info["letterSpacing"] = style["letterSpacing"]
            fill = _get_fill(node)
            if fill:
                info["color"] = fill
            return info

        def _get_layout_str(node: dict) -> str:
            """Build a layout description string from a node's auto-layout properties."""
            lm = node.get("layoutMode")
            if not lm:
                return ""
            direction = "row" if lm == "HORIZONTAL" else "column"
            parts = [f"flex:{direction}"]
            pa = node.get("primaryAxisAlignItems")
            ca = node.get("counterAxisAlignItems")
            if pa:
                parts.append(f"justify:{pa.lower()}")
            if ca:
                parts.append(f"align:{ca.lower()}")
            gap = node.get("itemSpacing")
            if gap:
                parts.append(f"gap:{round(gap,1)}px")
            pt = node.get("paddingTop")
            pb = node.get("paddingBottom")
            pl = node.get("paddingLeft")
            pr = node.get("paddingRight")
            if pt is not None and pt == pb and pl is not None and pl == pr and pt == pl and pt > 0:
                parts.append(f"pad:{round(pt,1)}px")
            elif pt is not None or pb is not None or pl is not None or pr is not None:
                p = f"{round(pt or 0,1)}px {round(pr or 0,1)}px {round(pb or 0,1)}px {round(pl or 0,1)}px"
                if p != "0px 0px 0px 0px":
                    parts.append(f"pad:{p}")
            return " ".join(parts)

        def _get_border_str(node: dict) -> str:
            """Build a border description string."""
            strokes = node.get("strokes", [])
            if not strokes or not isinstance(strokes, list):
                return ""
            weight = node.get("strokeWeight")
            if not weight:
                return ""
            for stroke in strokes:
                if isinstance(stroke, dict) and stroke.get("type") == "SOLID":
                    c = _fmt_color(stroke.get("color"), stroke.get("opacity"))
                    if c:
                        return f"border:{round(weight,1)}px solid {c}"
            return ""

        # ── Collect frames from canvases ──────────────────────

        def _get_canvases(node: dict) -> list[dict]:
            """Get all CANVAS nodes from the document."""
            if node.get("type") == "DOCUMENT":
                return node.get("children") or []
            return []

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

        canvases = _get_canvases(document)
        top_frames = _get_top_frames(document)

        # ── Select the best canvas to use ─────────────────────
        # Prefer the first canvas that has desktop-sized frames (>= 1024px wide)
        # or the canvas with the most frames

        def _frame_width(f: dict) -> float:
            bb = f.get("absoluteBoundingBox") or {}
            return float(bb.get("width", 0))

        def _is_desktop_frame(f: dict) -> bool:
            return _frame_width(f) >= 1024

        def _is_mobile_frame(f: dict) -> bool:
            w = _frame_width(f)
            return 0 < w < 600

        # Find the best canvas: prefer one with desktop frames
        selected_canvas_frames = top_frames
        for canvas in canvases:
            cframes = canvas.get("children") or []
            desktop_frames = [f for f in cframes if _is_desktop_frame(f)]
            if desktop_frames:
                selected_canvas_frames = cframes
                break

        # Filter: prefer desktop frames, fall back to largest frames
        desktop_frames = [f for f in selected_canvas_frames if _is_desktop_frame(f)]
        if desktop_frames:
            # Sort by area (largest first) and take top 8
            desktop_frames.sort(key=lambda f: _frame_width(f) * (f.get("absoluteBoundingBox") or {}).get("height", 0), reverse=True)
            working_frames = desktop_frames[:8]
        else:
            # No desktop frames — take the largest frames by area
            sorted_frames = sorted(
                selected_canvas_frames,
                key=lambda f: _frame_width(f) * (f.get("absoluteBoundingBox") or {}).get("height", 0),
                reverse=True,
            )
            working_frames = sorted_frames[:8]

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

        _scan(working_frames)

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

        for fi, frame in enumerate(working_frames):
            if estimated > MAX_OUTPUT_CHARS:
                lines.append(f"  ... ({len(working_frames) - fi} more sections omitted)")
                break

            fname = frame.get("name", f"section-{fi}")
            bbox = frame.get("absoluteBoundingBox") or {}
            fw = bbox.get("width")
            fh = bbox.get("height")
            fx = bbox.get("x", 0)
            fy = bbox.get("y", 0)
            dims = f" [{round(fw,1)}x{round(fh,1)}px]" if fw and fh else ""
            pos = f" @({round(fx,1)},{round(fy,1)})" if fx is not None and fy is not None else ""

            bg = _get_fill(frame)
            bg_str = f" bg:{bg}" if bg else ""

            is_img = _has_image_fill(frame)
            img_str = " [IMAGE]" if is_img else ""

            layout_str = _get_layout_str(frame)
            if layout_str:
                layout_str = f" {layout_str}"

            cr = frame.get("cornerRadius")
            radius_str = f" radius:{round(cr,1)}px" if cr and cr > 0 else ""

            border_str = _get_border_str(frame)
            if border_str:
                border_str = f" {border_str}"

            lines.append(f"  [{fi}] {fname}{dims}{pos}{bg_str}{img_str}{layout_str}{radius_str}{border_str}")
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
                cx = cbbox.get("x", 0)
                cy = cbbox.get("y", 0)
                cdims = f" [{round(cw,1)}x{round(ch,1)}px]" if cw and ch else ""
                cpos = f" @({round(cx,1)},{round(cy,1)})" if cx is not None and cy is not None else ""

                cbg = _get_fill(child)
                cbg_str = f" bg:{cbg}" if cbg else ""

                c_is_img = _has_image_fill(child)
                c_img_str = " [IMAGE]" if c_is_img else ""

                text = _get_text_info(child)
                text_str = ""
                if text:
                    t = text.get("text", "")
                    text_str = f" text:\"{t}\""
                    if text.get("font"):
                        text_str += f" font:{text['font']}"
                    if text.get("size"):
                        text_str += f" {text['size']}px"
                    if text.get("weight"):
                        text_str += f" weight:{text['weight']}"
                    if text.get("color"):
                        text_str += f" color:{text['color']}"
                    if text.get("align"):
                        text_str += f" align:{text['align']}"
                    if text.get("lineHeight"):
                        text_str += f" lh:{text['lineHeight']}px"
                    if text.get("letterSpacing"):
                        text_str += f" ls:{text['letterSpacing']}px"

                clayout_str = _get_layout_str(child)
                if clayout_str:
                    clayout_str = f" {clayout_str}"

                ccr = child.get("cornerRadius")
                cradius_str = f" radius:{round(ccr,1)}px" if ccr and ccr > 0 else ""

                cborder_str = _get_border_str(child)
                if cborder_str:
                    cborder_str = f" {cborder_str}"

                line = f"    - {cname}{cdims}{cpos}{cbg_str}{c_img_str}{text_str}{clayout_str}{cradius_str}{cborder_str}"
                lines.append(line)
                estimated += len(line)

        lines.append("")
        lines.append(
            "RULES:\n"
            "- Create index.html, style.css, script.js\n"
            "- index.html links style.css and script.js\n"
            "- Use the EXACT colors from the Colors list above\n"
            "- Use the EXACT fonts from the Fonts list above\n"
            "- Each [N] section is a top-level HTML section element\n"
            "- Indented children with '-' are nested inside their parent\n"
            "- Use the @(x,y) position data to place elements with CSS position:absolute\n"
            "  relative to their parent section. The parent section is positioned at (0,0).\n"
            "- For elements with flex:row or flex:column, use CSS flexbox instead of absolute\n"
            "- Match border-radius, border, and dimensions exactly\n"
            "- [IMAGE] markers mean the node has an image fill — use a colored div or inline SVG\n"
            "  as a placeholder. Do NOT use external image URLs.\n"
            "- Do NOT add, remove, or rearrange elements\n"
            "- Page must look IDENTICAL to the Figma design"
        )

        return "\n".join(lines)
