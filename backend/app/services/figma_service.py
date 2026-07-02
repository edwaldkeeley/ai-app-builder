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
    """
    header = response.headers.get("Retry-After")
    if header:
        try:
            return int(header)
        except ValueError:
            pass
        try:
            parsed = datetime.strptime(header, "%a, %d %b %Y %H:%M:%S %Z")
            now = datetime.now(timezone.utc)
            wait = (parsed.replace(tzinfo=timezone.utc) - now).total_seconds()
            if wait > 0:
                return int(wait)
        except ValueError:
            pass
    try:
        body = response.json()
        val = body.get("retry_after", body.get("Retry-After", default))
        return int(val)
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

        Produces a concise structured spec: page info, color palette, font palette,
        and a flat section list with key CSS properties. No nested trees.
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

        def _get_stroke(node: dict[str, Any]) -> str:
            strokes = node.get("strokes", [])
            weight = node.get("strokeWeight", 0)
            if isinstance(strokes, list) and strokes and weight:
                for s in strokes:
                    if isinstance(s, dict) and s.get("type") == "SOLID":
                        c = _fmt_color(s.get("color"))
                        if c:
                            return f"{weight}px solid {c}"
            return ""

        def _get_text_style(node: dict[str, Any]) -> dict | None:
            if node.get("type") != "TEXT":
                return None
            style = node.get("style", {}) or {}
            chars = node.get("characters", "")
            if len(chars) > 120:
                chars = chars[:120] + "..."
            result = {"text": chars}
            if style.get("fontFamily"):
                result["font-family"] = style["fontFamily"]
            if style.get("fontSize"):
                result["font-size"] = f"{style['fontSize']}px"
            if style.get("fontWeight"):
                result["font-weight"] = str(style["fontWeight"])
            if style.get("lineHeightPx"):
                result["line-height"] = f"{round(style['lineHeightPx'], 1)}px"
            if style.get("textAlignHorizontal") and style["textAlignHorizontal"] != "LEFT":
                result["text-align"] = style["textAlignHorizontal"].lower()
            fill = _get_fill(node)
            if fill:
                result["color"] = fill
            return result

        # ── Collect sections (top-level FRAMEs from the first canvas) ──

        def _collect_sections(node: dict, depth: int = 0) -> list[dict]:
            """Walk the tree and collect meaningful sections (FRAMEs, GROUPs, TEXTs)."""
            if depth > 30:
                return []
            nt = node.get("type", "")
            if nt == "DOCUMENT":
                results = []
                for c in (node.get("children") or []):
                    results.extend(_collect_sections(c, depth))
                return results
            if nt == "CANVAS":
                results = []
                for c in (node.get("children") or []):
                    results.extend(_collect_sections(c, depth))
                return results

            bbox = node.get("absoluteBoundingBox") or {}
            x, y, w, h = bbox.get("x"), bbox.get("y"), bbox.get("width"), bbox.get("height")
            node_name = node.get("name", "")

            entry = {
                "type": nt,
                "name": node_name,
                "x": round(x, 1) if x is not None else None,
                "y": round(y, 1) if y is not None else None,
                "w": round(w, 1) if w is not None else None,
                "h": round(h, 1) if h is not None else None,
            }

            bg = _get_fill(node)
            if bg:
                entry["bg"] = bg

            cr = node.get("cornerRadius")
            if cr and cr > 0:
                entry["border-radius"] = f"{round(cr,1)}px"

            border = _get_stroke(node)
            if border:
                entry["border"] = border

            lm = node.get("layoutMode")
            if lm:
                entry["layout"] = "row" if lm == "HORIZONTAL" else "column"
                pa = node.get("primaryAxisAlignItems")
                ca = node.get("counterAxisAlignItems")
                if pa:
                    entry["justify-content"] = pa.lower()
                if ca:
                    entry["align-items"] = ca.lower()
                gap = node.get("itemSpacing")
                if gap:
                    entry["gap"] = f"{round(gap,1)}px"
                pads = {}
                for k, css_k in [("paddingLeft", "left"), ("paddingRight", "right"),
                                 ("paddingTop", "top"), ("paddingBottom", "bottom")]:
                    v = node.get(k, 0)
                    if v:
                        pads[css_k] = f"{round(v,1)}px"
                if pads:
                    entry["padding"] = pads

            text = _get_text_style(node)
            if text:
                entry["text"] = text

            children = node.get("children")
            if children:
                child_sections = []
                for c in children:
                    child_sections.extend(_collect_sections(c, depth + 1))
                if child_sections:
                    entry["children"] = child_sections

            return [entry]

        sections = _collect_sections(document)

        # ── Extract unique colors and fonts ────────────────────

        def _walk_colors(items: list, seen: set) -> list[str]:
            colors = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if "bg" in item and item["bg"] not in seen:
                    seen.add(item["bg"])
                    colors.append(item["bg"])
                if "text" in item and isinstance(item["text"], dict) and "color" in item["text"]:
                    c = item["text"]["color"]
                    if c not in seen:
                        seen.add(c)
                        colors.append(c)
                if "border" in item:
                    # Extract color from "Npx solid COLOR"
                    parts = item["border"].split()
                    if len(parts) >= 3:
                        c = parts[-1]
                        if c not in seen:
                            seen.add(c)
                            colors.append(c)
                for c in (item.get("children") or []):
                    colors.extend(_walk_colors([c], seen))
            return colors

        def _walk_fonts(items: list, seen: set) -> list[dict]:
            fonts = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                if "text" in item and isinstance(item["text"], dict):
                    ff = item["text"].get("font-family")
                    fs = item["text"].get("font-size")
                    fw = item["text"].get("font-weight")
                    if ff and ff not in seen:
                        seen.add(ff)
                        entry = {"font-family": ff}
                        if fs:
                            entry["font-size"] = fs
                        if fw:
                            entry["font-weight"] = fw
                        fonts.append(entry)
                for c in (item.get("children") or []):
                    fonts.extend(_walk_fonts([c], seen))
            return fonts

        all_colors = _walk_colors(sections, set())
        all_fonts = _walk_fonts(sections, set())

        # ── Build a compact YAML-like spec ─────────────────────

        def _format_spec(items: list, indent: int = 0) -> str:
            pad = "  " * indent
            lines = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = item.get("name", item.get("type", "?"))
                tag = item["type"].lower().replace("_", "-")
                dims = ""
                if item.get("w") and item.get("h"):
                    dims = f" [{item['w']}x{item['h']}px]"
                lines.append(f"{pad}- {tag} \"{name}\"{dims}")
                if item.get("bg"):
                    lines.append(f"{pad}  bg: {item['bg']}")
                if item.get("border-radius"):
                    lines.append(f"{pad}  radius: {item['border-radius']}")
                if item.get("border"):
                    lines.append(f"{pad}  border: {item['border']}")
                if item.get("layout"):
                    lines.append(f"{pad}  flex: {item['layout']}")
                    if item.get("justify-content"):
                        lines.append(f"{pad}  justify: {item['justify-content']}")
                    if item.get("align-items"):
                        lines.append(f"{pad}  align: {item['align-items']}")
                    if item.get("gap"):
                        lines.append(f"{pad}  gap: {item['gap']}")
                    if item.get("padding"):
                        p = item["padding"]
                        parts = []
                        for k in ("top", "right", "bottom", "left"):
                            if k in p:
                                parts.append(p[k])
                            else:
                                parts.append("0")
                        if any(v != "0" for v in parts):
                            lines.append(f"{pad}  padding: {' '.join(parts)}")
                if item.get("text"):
                    t = item["text"]
                    lines.append(f"{pad}  text: \"{t.get('text', '')}\"")
                    if t.get("font-family"):
                        lines.append(f"{pad}  font: {t['font-family']} {t.get('font-size', '')} {t.get('font-weight', '')}")
                    if t.get("color"):
                        lines.append(f"{pad}  color: {t['color']}")
                    if t.get("text-align"):
                        lines.append(f"{pad}  align: {t['text-align']}")
                if item.get("children"):
                    child_text = _format_spec(item["children"], indent + 1)
                    if child_text:
                        lines.append(child_text)
            return "\n".join(lines)

        spec = _format_spec(sections)

        # ── Build prompt ────────────────────────────────────────
        parts = [
            f"Design: {name}",
            "",
            "Convert this Figma design to HTML + CSS + JS.",
            "",
        ]

        if all_colors:
            parts.append("Colors:")
            for c in all_colors[:15]:
                parts.append(f"  - {c}")
            parts.append("")

        if all_fonts:
            parts.append("Fonts:")
            for f in all_fonts[:10]:
                parts.append(f"  - {f['font-family']} {f.get('font-size', '')} {f.get('font-weight', '')}")
            parts.append("")

        parts.append("Sections:")
        parts.append(spec)
        parts.append("")
        parts.append(
            "Rules:\n"
            "- Create index.html, style.css, script.js\n"
            "- index.html links style.css and script.js\n"
            "- Use exact colors, fonts, sizes from the spec\n"
            "- Use flexbox with exact direction, justify, align, gap, padding\n"
            "- Match border-radius, border exactly\n"
            "- Do NOT add/remove/rearrange elements\n"
            "- Use colored divs or SVG for images (no external URLs)\n"
            "- Page must look IDENTICAL to the Figma design"
        )

        return "\n".join(parts)
