"""Figma node tree walking and design prompt builder.

Builds a compact text summary of the Figma design tree and assembles it
into a structured prompt for AI code generation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.services.figma_filter import (
    filter_figma_data,
    get_canvases,
    get_canvas_dimensions,
    classify_canvas,
)
from app.services.figma_types import get_solid_color, get_text_color, rgb_to_hex

logger = logging.getLogger(__name__)


def walk_nodes(
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
    bg_color = get_solid_color(node.get("fills"))
    text_color = get_text_color(node)

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
        stroke_color = get_solid_color(strokes)

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
                sh_color = rgb_to_hex(sc.get("r", 0), sc.get("g", 0), sc.get("b", 0))
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
                    hex1 = rgb_to_hex(c1.get("r", 0), c1.get("g", 0), c1.get("b", 0))
                    hex2 = rgb_to_hex(c2.get("r", 0), c2.get("g", 0), c2.get("b", 0))
                    gtype = f.get("gradientType", "LINEAR")
                    parts.append(f"gradient:{gtype} {hex1}->{hex2}")

    lines.append(" ".join(parts))

    # Recurse into children
    children = node.get("children", [])
    if children:
        for child in children:
            child_lines = walk_nodes(child, depth + 1, x, y)
            lines.extend(child_lines)

    return lines


def build_design_prompt(
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

    canvases = get_canvases(document)
    canvas_labels: dict[int, str] = {}
    for i, canvas in enumerate(canvases):
        label = classify_canvas(canvas)
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
        w, h = get_canvas_dimensions(canvas)
        lines.append(f"### Canvas: \"{canvas_name}\" ({label}, {w:.0f}x{h:.0f}px)")
        lines.append("")
        tree_lines = walk_nodes(canvas)
        # Cap tree summary at 100k chars to keep total prompt manageable
        tree_text = "\n".join(tree_lines)
        if len(tree_text) > 100_000:
            tree_text = tree_text[:100_000] + "\n  // ... [tree truncated]"
        lines.append(tree_text)
        lines.append("")

    # ── Part 2: Filtered Figma JSON ─────────────────────────

    lines.append("## Filtered Figma JSON (for reference)")
    lines.append("")
    filtered_data = filter_figma_data(file_data)
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
        "Use the Design Tree Summary as your primary reference. "
        "Use the Filtered Figma JSON for additional detail.\n"
        "\n"
        + viewport_instruction + "\n"
        "### Node rendering guide\n"
        "\n"
        "- [RECTANGLE] -> <div> (background or decoration)\n"
        "- [ELLIPSE] -> <div> with border-radius: 50%\n"
        "- [VECTOR] -> small colored <div> or inline SVG\n"
        "- [GROUP] -> <div> container\n"
        "- [TEXT] -> text with the exact font, size, weight, and color\n"
        "- [FRAME] -> <div> section or container\n"
        "\n"
        "### Positioning\n"
        "\n"
        "- @(x,y) values are relative to the parent node.\n"
        "- Use `position: absolute; left: Xpx; top: Ypx` for each element.\n"
        "- The top-level FRAME uses `position: relative` as the main container.\n"
        "- For FRAME nodes with a layoutMode (HORIZONTAL/VERTICAL), use CSS flexbox.\n"
        "\n"
        "### Output\n"
        "\n"
        "1. Create index.html, style.css, and script.js\n"
        "2. Use the exact colors, fonts, dimensions, and effects from the summary\n"
        "3. Include every node from the summary in your HTML — do not skip any\n"
        "4. Do not add, remove, or rearrange elements\n"
        "5. Center the design in the viewport (`margin: 0 auto` on the main container)\n"
        "6. Position elements precisely using the @ coordinates\n"
        "7. Use the exact hex colors from the summary\n"
        "8. Render every text node with the specified font, size, weight, and color\n"
        "9. Apply shadows and corner radii exactly as specified\n"
        "10. Use flexbox for FRAME nodes with layoutMode\n"
        "11. Canvas-level elements should use `position: relative` as the root container\n"
        "\n"
        "Output valid JSON with: {\"files\": [{\"path\": \"index.html\", \"content\": \"...\", \"file_type\": \"html\"}, ...], \"message\": \"description of what was built\"}"
    )

    return "\n".join(lines)
