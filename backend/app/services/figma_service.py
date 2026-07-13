"""Figma API integration service.

Provides Figma REST API access for fetching file data via personal access
token or direct API calls, and a design-to-prompt converter that feeds into
the existing AI generation pipeline.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FIGMA_API_URL = "https://api.figma.com/v1"

# Max retries for Figma API 429 responses
_FIGMA_MAX_RETRIES = 1  # only retry once — don't burn through rate limit

# In-memory cache for Figma file responses
# Key: file_key, Value: (timestamp, response_data)
_figma_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_FIGMA_CACHE_TTL = 300  # 5 minutes

# Rate limiter: track last request time per token
_last_request_time: float = 0
_MIN_REQUEST_INTERVAL = 2.0  # minimum 2 seconds between requests

# Disk cache directory for Figma file responses (survives restarts)
_FIGMA_DISK_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".figma_cache",
)
_FIGMA_DISK_CACHE_TTL = 86400 * 7  # 7 days


def _disk_cache_path(file_key: str) -> str:
    """Get the disk cache file path for a Figma file key."""
    os.makedirs(_FIGMA_DISK_CACHE_DIR, exist_ok=True)
    # Sanitize file key for filesystem
    safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", file_key)
    return os.path.join(_FIGMA_DISK_CACHE_DIR, f"{safe_key}.json")


def _read_disk_cache(file_key: str) -> dict[str, Any] | None:
    """Read Figma data from disk cache if it exists and is not expired."""
    path = _disk_cache_path(file_key)
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            cached = json.load(f)
        cache_time = cached.get("_cached_at", 0)
        if time.time() - cache_time > _FIGMA_DISK_CACHE_TTL:
            logger.info("Figma disk cache EXPIRED for file key: %s", file_key)
            os.remove(path)
            return None
        logger.info("Figma disk cache HIT for file key: %s", file_key)
        return cached.get("data")
    except Exception as e:
        logger.warning("Figma disk cache read error for %s: %s", file_key, e)
        return None


def _write_disk_cache(file_key: str, data: dict[str, Any]) -> None:
    """Write Figma data to disk cache."""
    try:
        path = _disk_cache_path(file_key)
        cached = {
            "_cached_at": time.time(),
            "_file_key": file_key,
            "data": data,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cached, f, ensure_ascii=False)
        size_mb = len(json.dumps(data)) / 1024 / 1024
        logger.info("Figma disk cache WRITTEN for file key: %s (%.1f MB)", file_key, size_mb)
    except Exception as e:
        logger.warning("Figma disk cache write error for %s: %s", file_key, e)


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
        """Make a Figma API request with caching, rate limiting, and 429 retry logic.

        Features:
        - **In-memory cache**: Repeated requests for the same file within 5 minutes
          return cached data instead of hitting the API.
        - **Rate limiting**: Enforces a minimum 2-second gap between requests to
          avoid hitting Figma's aggressive rate limits.
        - **Single retry**: Only retries once on 429 (retrying more just burns
          through the rate limit faster).
        - **Fails fast**: On 429, raises ``FigmaRateLimitError`` immediately
          with the retry-after duration.
        """
        global _last_request_time

        # ── Rate limiting: enforce minimum gap between requests ──
        now = time.time()
        since_last = now - _last_request_time
        if since_last < _MIN_REQUEST_INTERVAL and _last_request_time > 0:
            wait = _MIN_REQUEST_INTERVAL - since_last
            logger.debug("Rate limiter: waiting %.1fs before Figma API call", wait)
            await asyncio.sleep(wait)
        _last_request_time = time.time()

        # ── Check cache for GET requests ─────────────────────────
        is_file_request = "v1/files/" in url and method.upper() == "GET"
        if is_file_request:
            # Extract file key from URL
            file_key_match = re.search(r"/files/([^/?#]+)", url)
            if file_key_match:
                file_key = file_key_match.group(1)

                # 1. Check in-memory cache first
                cached = _figma_cache.get(file_key)
                if cached:
                    cache_time, cache_data = cached
                    if time.time() - cache_time < _FIGMA_CACHE_TTL:
                        logger.info("Figma memory cache HIT for file key: %s", file_key)
                        return httpx.Response(
                            status_code=200,
                            json=cache_data,
                            request=httpx.Request(method, url),
                        )

                # 2. Check disk cache (survives restarts)
                disk_data = _read_disk_cache(file_key)
                if disk_data is not None:
                    # Populate in-memory cache too
                    _figma_cache[file_key] = (time.time(), disk_data)
                    return httpx.Response(
                        status_code=200,
                        json=disk_data,
                        request=httpx.Request(method, url),
                    )

                logger.info("Figma cache MISS for file key: %s", file_key)

        # ── Make the request ─────────────────────────────────────
        for attempt in range(_FIGMA_MAX_RETRIES + 1):
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method, url, headers=headers)

            if response.status_code == 429:
                wait = _parse_retry_after(response)
                # Fail fast — don't retry, just tell the user to wait
                raise FigmaRateLimitError(
                    retry_after=wait,
                    message=f"Figma API rate limited (429). Retry after {wait}s. "
                    "Personal access tokens have strict rate limits. "
                    "Wait and try again, or use a different token.",
                )

            if not response.is_success:
                raise FigmaApiError(
                    status=response.status_code,
                    detail=f"Figma API returned {response.status_code}: {response.text[:500]}",
                )

            # ── Cache the response for GET file requests ─────────
            if is_file_request and file_key_match:
                file_key = file_key_match.group(1)
                try:
                    data = response.json()
                    _figma_cache[file_key] = (time.time(), data)
                    # Also persist to disk so it survives restarts
                    _write_disk_cache(file_key, data)
                    logger.info("Figma cache SET for file key: %s (%.1f MB)", file_key, len(json.dumps(data)) / 1024 / 1024)
                except Exception:
                    pass

            return response

        # Should not be reached
        raise FigmaRateLimitError(retry_after=60)

    @staticmethod
    def clear_cache(file_key: str | None = None) -> int:
        """Clear the Figma file cache (memory + disk).

        Args:
            file_key: If provided, only clear the cache for this specific file.
                      If None, clear the entire cache.

        Returns:
            Number of cache entries cleared.
        """
        global _figma_cache
        cleared = 0
        if file_key:
            # Clear memory
            if file_key in _figma_cache:
                del _figma_cache[file_key]
                cleared += 1
            # Clear disk
            disk_path = _disk_cache_path(file_key)
            if os.path.exists(disk_path):
                try:
                    os.remove(disk_path)
                    cleared += 1
                except Exception as e:
                    logger.warning("Failed to remove disk cache for %s: %s", file_key, e)
            logger.info("Figma cache cleared for file key: %s (%d entries)", file_key, cleared)
            return cleared
        # Clear all
        count = len(_figma_cache)
        _figma_cache.clear()
        # Clear all disk cache files
        if os.path.exists(_FIGMA_DISK_CACHE_DIR):
            for fname in os.listdir(_FIGMA_DISK_CACHE_DIR):
                if fname.endswith(".json"):
                    try:
                        os.remove(os.path.join(_FIGMA_DISK_CACHE_DIR, fname))
                        cleared += 1
                    except Exception:
                        pass
        logger.info("Figma cache cleared entirely (%d memory + %d disk)", count, cleared)
        return count + cleared

    @staticmethod
    def get_cache_info() -> dict[str, Any]:
        """Get cache statistics."""
        global _figma_cache
        return {
            "entries": len(_figma_cache),
            "keys": list(_figma_cache.keys()),
            "ttl_seconds": _FIGMA_CACHE_TTL,
        }

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

    # ── Figma JSON filter ──────────────────────────────────────

    @staticmethod
    def _filter_figma_data(file_data: dict[str, Any]) -> dict[str, Any]:
        """Strip irrelevant data from the Figma API response.

        The Figma API returns massive JSON blobs (often 10M+ chars) with lots
        of data that's useless for code generation:
        - ``components`` — reusable component definitions (not needed for one-off gen)
        - ``componentSets`` — component set definitions
        - ``componentMetadata`` — published component references
        - ``styles`` — color/text/effect style definitions (info is in the nodes)
        - ``pluginData`` — Figma plugin metadata
        - ``documentation`` — descriptions and docs
        - Image fills — base64 image data and URLs (we use colored div placeholders)
        - Hidden layers — invisible in the design, shouldn't be rendered

        This filter keeps only what the AI needs: node structure, positions,
        sizes, colors, text, fonts, and effects.
        """
        filtered: dict[str, Any] = {}

        # Keep top-level metadata
        for key in ("name", "lastModified", "thumbnailUrl", "version"):
            if key in file_data:
                filtered[key] = file_data[key]

        # Filter the document tree recursively
        document = file_data.get("document")
        if document and isinstance(document, dict):
            filtered["document"] = FigmaService._filter_node(document)

        return filtered

    @staticmethod
    def _filter_node(node: dict[str, Any]) -> dict[str, Any]:
        """Recursively filter a Figma node, keeping only relevant properties.

        Strips: image fills, plugin data, component references, export settings,
        transition info, and other metadata not needed for code generation.
        """
        result: dict[str, Any] = {}

        # Always keep structural fields
        for key in ("id", "type", "name", "visible"):
            if key in node:
                result[key] = node[key]

        # Keep bounding box
        if "absoluteBoundingBox" in node:
            result["absoluteBoundingBox"] = node["absoluteBoundingBox"]

        # Keep constraints (for responsive behavior hints)
        if "constraints" in node:
            result["constraints"] = node["constraints"]

        # Keep corner radius
        if "cornerRadius" in node:
            result["cornerRadius"] = node["cornerRadius"]
        if "individualCornerRadius" in node:
            result["individualCornerRadius"] = node["individualCornerRadius"]

        # Keep stroke info
        if "strokeWeight" in node:
            result["strokeWeight"] = node["strokeWeight"]
        if "strokeAlign" in node:
            result["strokeAlign"] = node["strokeAlign"]
        if "strokes" in node:
            result["strokes"] = FigmaService._filter_fills(node["strokes"])

        # Keep fills — but STRIP image fills (they contain massive base64 data)
        if "fills" in node:
            result["fills"] = FigmaService._filter_fills(node["fills"])

        # Keep effects (shadows, blurs) — strip image effects
        if "effects" in node:
            result["effects"] = FigmaService._filter_effects(node["effects"])

        # Keep opacity and blend mode
        for key in ("opacity", "blendMode"):
            if key in node:
                result[key] = node[key]

        # Keep clipping info
        if "clipsContent" in node:
            result["clipsContent"] = node["clipsContent"]

        # Keep layout properties (auto-layout / flexbox)
        for key in (
            "layoutMode", "primaryAxisAlignItems", "counterAxisAlignItems",
            "itemSpacing", "itemReverseZIndex", "layoutWrap",
            "paddingLeft", "paddingRight", "paddingTop", "paddingBottom",
            "counterAxisSizingMode", "primaryAxisSizingMode",
        ):
            if key in node:
                result[key] = node[key]

        # Keep text content and style
        if "characters" in node:
            result["characters"] = node["characters"]
        if "style" in node:
            style = node["style"]
            # Only keep relevant text style fields
            result["style"] = {
                k: style[k] for k in (
                    "fontFamily", "fontPostScriptName", "fontSize", "fontWeight",
                    "textAlignHorizontal", "textAlignVertical",
                    "lineHeightPx", "letterSpacing",
                    "paragraphSpacing", "paragraphIndent",
                    "textCase", "textDecoration",
                ) if k in style
            }

        # Keep isMask for mask nodes
        if "isMask" in node:
            result["isMask"] = node["isMask"]

        # Recursively filter children
        children = node.get("children")
        if children and isinstance(children, list):
            filtered_children = []
            for child in children:
                if isinstance(child, dict):
                    filtered_children.append(FigmaService._filter_node(child))
            if filtered_children:
                result["children"] = filtered_children

        return result

    @staticmethod
    def _filter_fills(fills: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter fill/stroke entries, stripping image data.

        Image fills contain massive base64-encoded image data that we don't
        need — we tell the AI to use colored div placeholders instead.
        """
        filtered = []
        for f in fills:
            entry: dict[str, Any] = {}
            entry["type"] = f.get("type", "SOLID")
            entry["opacity"] = f.get("opacity", 1)

            if entry["type"] == "SOLID":
                entry["color"] = f.get("color", {})
            elif entry["type"] == "GRADIENT":
                entry["gradientType"] = f.get("gradientType", "LINEAR")
                entry["gradientStops"] = f.get("gradientStops", [])
            elif entry["type"] == "IMAGE":
                # Strip image data — keep only the fact that it's an image fill
                entry["scaleMode"] = f.get("scaleMode", "FILL")
                # Do NOT include imageRef, imageTransform, or any base64 data
            else:
                # Keep unknown fill types as-is but strip image data
                for k, v in f.items():
                    if k not in ("imageRef", "imageTransform", "imageData"):
                        entry[k] = v

            filtered.append(entry)
        return filtered

    @staticmethod
    def _filter_effects(effects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter effects, keeping only relevant properties."""
        filtered = []
        for e in effects:
            entry: dict[str, Any] = {}
            entry["type"] = e.get("type", "INNER_SHADOW")
            entry["visible"] = e.get("visible", True)
            entry["radius"] = e.get("radius", 0)

            if entry["type"] in ("DROP_SHADOW", "INNER_SHADOW"):
                entry["color"] = e.get("color", {})
                entry["offset"] = e.get("offset", {})
                entry["spread"] = e.get("spread", 0)
            elif entry["type"] == "LAYER_BLUR":
                pass  # radius is already set
            elif entry["type"] == "BACKGROUND_BLUR":
                pass

            filtered.append(entry)
        return filtered

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

    # ── Canvas selection ───────────────────────────────────────

    @staticmethod
    def _get_canvases(document: dict) -> list[dict]:
        """Extract all CANVAS nodes from the document tree.

        Figma files often have multiple canvases (Desktop, Mobile, Tablet).
        Returns them all so the AI can generate responsive code.
        """
        canvases: list[dict] = []
        children = document.get("children", [])
        for child in children:
            if isinstance(child, dict) and child.get("type") == "CANVAS":
                canvases.append(child)
        return canvases

    @staticmethod
    def _get_canvas_dimensions(canvas: dict) -> tuple[float, float]:
        """Get the effective dimensions of a canvas by looking at its top-level FRAMEs."""
        max_w = 0.0
        max_h = 0.0
        for child in canvas.get("children", []):
            if isinstance(child, dict):
                bbox = child.get("absoluteBoundingBox") or {}
                w = bbox.get("width", 0) or 0
                h = bbox.get("height", 0) or 0
                if w > max_w:
                    max_w = w
                if h > max_h:
                    max_h = h
        return max_w, max_h

    @staticmethod
    def _classify_canvas(canvas: dict) -> str:
        """Classify a canvas as 'desktop', 'tablet', 'mobile', or 'unknown' based on name and dimensions."""
        name = (canvas.get("name") or "").lower()
        w, h = FigmaService._get_canvas_dimensions(canvas)

        # Check name first
        if any(kw in name for kw in ("desktop", "web", "laptop", "1440", "1920")):
            return "desktop"
        if any(kw in name for kw in ("mobile", "phone", "iphone", "android", "375", "390", "414")):
            return "mobile"
        if any(kw in name for kw in ("tablet", "ipad", "768", "834")):
            return "tablet"

        # Fall back to width heuristic
        if w >= 1024:
            return "desktop"
        if w >= 600:
            return "tablet"
        if w > 0:
            return "mobile"

        return "unknown"

    # ── Design prompt builder ─────────────────────────────────

    def build_design_prompt(
        self,
        file_data: dict[str, Any],
    ) -> str:
        """Build a prompt with a Design Tree Summary + Filtered Figma JSON.

        The Figma JSON is filtered to remove irrelevant data (image fills,
        components, styles, plugin data) before serialization.
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

        # ── Identify canvases ────────────────────────────────────

        canvases = FigmaService._get_canvases(document)
        canvas_labels: dict[int, str] = {}
        for i, canvas in enumerate(canvases):
            label = FigmaService._classify_canvas(canvas)
            canvas_labels[i] = label

        canvas_info = ", ".join(
            f'"{c.get("name", "?")}" -> {canvas_labels[i]}'
            for i, c in enumerate(canvases)
        )
        logger.info("Figma canvases detected: %s", canvas_info)

        unique_types = set(canvas_labels.values())
        all_same_type = len(unique_types) <= 1 and len(canvases) > 1
        has_multiple = len(canvases) > 1

        # ── Part 1: Design Tree Summary ─────────────────────────

        lines: list[str] = []
        lines.append(f"# Figma Design: {name}")
        if last_modified:
            lines.append(f"Last modified: {last_modified}")
        lines.append("")
        lines.append("## Design Tree Summary")
        lines.append("")
        lines.append(
            "Each line shows: [TYPE] \"name\" @(x,y) widthxheight "
            "bg:color br:radius bd:stroke shadow:offset color:text-properties"
        )
        lines.append("")

        for i, canvas in enumerate(canvases):
            label = canvas_labels.get(i, "unknown")
            canvas_name = canvas.get("name", f"Canvas {i}")
            w, h = FigmaService._get_canvas_dimensions(canvas)
            lines.append(f"### Canvas: \"{canvas_name}\" ({label}, {w:.0f}x{h:.0f}px)")
            lines.append("")
            tree_lines = FigmaService._walk_nodes(canvas)
            # Cap tree summary at 100k chars to keep total prompt manageable
            tree_text = "\n".join(tree_lines)
            if len(tree_text) > 100_000:
                tree_text = tree_text[:100_000] + "\n  // ... [tree truncated]"
            lines.append(tree_text)
            lines.append("")

        # ── Part 2: Filtered Figma JSON ─────────────────────────

        lines.append("## Filtered Figma JSON (for reference)")
        lines.append("")
        filtered_data = FigmaService._filter_figma_data(file_data)
        raw_json = json.dumps(filtered_data, indent=2, ensure_ascii=False)
        if len(raw_json) > 40_000:
            raw_json = raw_json[:40_000] + "\n  // ... [JSON truncated]"
        lines.append("```json")
        lines.append(raw_json)
        lines.append("```")
        lines.append("")

        # ── Part 3: Instructions ────────────────────────────────

        if has_multiple and all_same_type:
            canvas_list = "\n".join(
                f'  {i+1}. "{c.get("name", f"Canvas {i}")}"'
                for i, c in enumerate(canvases)
            )
            viewport_instruction = (
                "This design has multiple canvases that are DIFFERENT PAGES of the same website.\n"
                f"{canvas_list}\n"
                "Generate a SINGLE HTML file (index.html) with ALL pages. "
                "Render ALL nodes from the tree — do not skip any elements. "
                "Use your judgment on the best layout: stack them vertically for a scrolling page, "
                "or use JavaScript section switching if the design has a navigation bar.\n"
            )
        elif has_multiple:
            viewport_instruction = (
                "This design has multiple canvases for different viewports.\n"
                "Generate a SINGLE responsive HTML page with CSS media queries.\n"
            )
        else:
            viewport_instruction = "Generate code that matches this design exactly.\n"

        lines.append(
            "## Instructions\n"
            "\n"
            "Use the Design Tree Summary as your PRIMARY reference. "
            "The Filtered Figma JSON is for additional detail.\n"
            "\n"
            + viewport_instruction + "\n"
            "### Node rendering guide\n"
            "\n"
            "- [RECTANGLE] → <div> (background or decoration)\n"
            "- [ELLIPSE] → <div> with border-radius:50%\n"
            "- [VECTOR] → small colored <div> or inline SVG\n"
            "- [GROUP] → <div> container (positions children)\n"
            "- [TEXT] → text with exact font, size, weight, color\n"
            "- [FRAME] → <div> section/container\n"
            "\n"
            "### Positioning\n"
            "\n"
            "- @(x,y) values are RELATIVE to the parent node.\n"
            "- Use `position: absolute; left: Xpx; top: Ypx` for each element.\n"
            "- The top-level FRAME is the main container — use `position: relative`.\n"
            "- For FRAME nodes with layoutMode (HORIZONTAL/VERTICAL), use CSS flexbox.\n"
            "\n"
            "### Output\n"
            "\n"
            "1. Create index.html, style.css, and script.js\n"
            "2. Use EXACT colors, fonts, dimensions, border-radius, and effects from the summary\n"
            "3. Every node in the summary must appear in your HTML — do not skip any\n"
            "4. Do NOT add, remove, or rearrange elements\n"
            "5. Center the design in the viewport (use margin: 0 auto on the main container)\n"
            "6. Page must look IDENTICAL to the Figma design"
        )

        return "\n".join(lines)
