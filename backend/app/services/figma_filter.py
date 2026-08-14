"""Figma JSON filtering, URL parsing, and canvas detection.

All functions are pure — no state, no IO. They operate on Figma API response
data structures and return transformed copies.
"""

from __future__ import annotations

import re
from typing import Any


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


def filter_figma_data(file_data: dict[str, Any]) -> dict[str, Any]:
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
        filtered["document"] = _filter_node(document)

    return filtered


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
        result["strokes"] = _filter_fills(node["strokes"])

    # Keep fills — but STRIP image fills (they contain massive base64 data)
    if "fills" in node:
        result["fills"] = _filter_fills(node["fills"])

    # Keep effects (shadows, blurs) — strip image effects
    if "effects" in node:
        result["effects"] = _filter_effects(node["effects"])

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
                filtered_children.append(_filter_node(child))
        if filtered_children:
            result["children"] = filtered_children

    return result


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
        elif entry["type"] in ("LAYER_BLUR", "BACKGROUND_BLUR"):
            pass  # radius is already set

        filtered.append(entry)
    return filtered


# ── Canvas detection ───────────────────────────────────────────


def get_canvases(document: dict) -> list[dict]:
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


def get_canvas_dimensions(canvas: dict) -> tuple[float, float]:
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


def classify_canvas(canvas: dict) -> str:
    """Classify a canvas as 'desktop', 'tablet', 'mobile', or 'unknown' based on name and dimensions."""
    name = (canvas.get("name") or "").lower()
    w, h = get_canvas_dimensions(canvas)

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
