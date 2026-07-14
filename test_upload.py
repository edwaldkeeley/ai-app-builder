"""Test the design upload two-stage pipeline directly.

Stage 1: Sends an image to the vision model and parses the DesignSpec.
Stage 2: Sends the DesignSpec to the main model and generates full code.

Usage:
    python test_upload.py                          # generated test image
    python test_upload.py my_design.png             # your own image
    python test_upload.py my_design.png "dark mode" # with a prompt
"""

import base64
import io
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent / ".env")


def create_test_png(width=200, height=150, r=66, g=133, b=244):
    """Generate a simple solid-color PNG."""
    import struct
    import zlib

    def chunk(t, d):
        c = t + d
        return struct.pack(">I", len(d)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    raw = b""
    for _ in range(height):
        raw += b"\x00"
        for _ in range(width):
            raw += struct.pack("BBB", r, g, b)
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _resize_image(image_bytes, mime):
    """Resize and compress image for the vision model's small context window."""
    if not HAS_PIL:
        return image_bytes, mime

    img = PILImage.open(io.BytesIO(image_bytes))
    w, h = img.size
    max_dim = 150
    if w > max_dim or h > max_dim:
        ratio = max_dim / max(w, h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), PILImage.LANCZOS)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=30, optimize=True)
    result = buf.getvalue()
    print(f"  Resized: {w}x{h} -> {new_w}x{new_h} ({len(result)} bytes, JPEG q30)")
    return result, "image/jpeg"


def _call_ai(target_url, jwt_token, model, payload, label="AI"):
    """Make a streaming API call and return the accumulated content."""
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/json",
    }

    print(f"\n  [{label}] Sending request ({len(json.dumps(payload))} chars)...")
    print(f"  [{label}] Model: {model}")
    print(f"  [{label}] Waiting for response...\n")

    full_text = ""
    with httpx.Client(timeout=300) as client:
        with client.stream("POST", target_url, json=payload, headers=headers) as response:
            print(f"  Status: {response.status_code}")

            if response.status_code != 200:
                print(f"  ERROR: ", end="")
                for chunk in response.iter_bytes():
                    print(chunk.decode(), end="")
                print()
                return None

            for chunk in response.iter_lines():
                if chunk.startswith("data: "):
                    data = chunk[6:]
                    if data == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data)
                        delta = parsed.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_text += content
                            print(content, end="", flush=True)
                    except json.JSONDecodeError:
                        pass

    print("\n")
    return full_text


def _extract_json(text):
    """Extract the first JSON object from text."""
    try:
        start = text.index("{")
        end = text.rindex("}")
        return json.loads(text[start : end + 1])
    except (ValueError, json.JSONDecodeError) as e:
        print(f"  Could not parse JSON: {e}")
        return None


def main():
    # ── Parse args ────────────────────────────────────────────
    image_path = None
    user_prompt = ""

    for arg in sys.argv[1:]:
        if arg.startswith("--prompt="):
            user_prompt = arg.split("=", 1)[1]
        elif not arg.startswith("--"):
            image_path = arg

    # ── Read config from env ──────────────────────────────────
    vision_target = os.getenv("DESIGN_UPLOAD_TARGET_URL") or os.getenv("TARGET_URL")
    vision_token = os.getenv("DESIGN_UPLOAD_JWT_TOKEN") or os.getenv("JWT_TOKEN")
    vision_model = os.getenv("DESIGN_UPLOAD_MODEL") or os.getenv("MODEL")

    main_target = os.getenv("TARGET_URL")
    main_token = os.getenv("JWT_TOKEN")
    main_model = os.getenv("MODEL")

    if not vision_target or not vision_token or not vision_model:
        print("ERROR: Missing AI provider config for vision model.")
        print("Set DESIGN_UPLOAD_TARGET_URL, DESIGN_UPLOAD_JWT_TOKEN, DESIGN_UPLOAD_MODEL in .env")
        sys.exit(1)

    if not main_target or not main_token or not main_model:
        print("ERROR: Missing AI provider config for main model.")
        print("Set TARGET_URL, JWT_TOKEN, MODEL in .env")
        sys.exit(1)

    print("=" * 60)
    print("TWO-STAGE DESIGN UPLOAD TEST")
    print("=" * 60)
    print(f"Vision model: {vision_model} ({vision_target})")
    print(f"Main model:   {main_model} ({main_target})")
    print()

    # ── Load or generate image ────────────────────────────────
    if image_path:
        path = Path(image_path)
        if not path.exists():
            print(f"File not found: {image_path}")
            sys.exit(1)
        image_bytes = path.read_bytes()
        mime = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
        }.get(path.suffix.lower(), "image/png")
        print(f"Image: {path.name} ({len(image_bytes)} bytes, {mime})")
    else:
        image_bytes = create_test_png()
        mime = "image/png"
        print(f"Image: generated test image ({len(image_bytes)} bytes, {mime})")

    # Resize for vision model
    image_bytes, mime = _resize_image(image_bytes, mime)

    # Build data URI
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_uri = f"data:{mime};base64,{b64}"

    # ════════════════════════════════════════════════════════════
    # STAGE 1: Vision model → DesignSpec
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("STAGE 1: Vision Model → Design Spec")
    print("=" * 60)

    stage1_prompt = (
        "Analyze this design image and output a structured JSON spec.\n"
        f"Filename: {Path(image_path).name if image_path else 'test_design'}\n"
        f"Type: {mime}\n"
        f"Image (data URI):\n{data_uri}"
    )

    stage1_system = (
        "You are a design analyzer. Your job is to look at the provided design image and output a "
        "structured JSON description of what you see. Do NOT write any code.\n\n"
        "### What to extract\n"
        "- **layout**: Overall layout type (e.g. 'centered single column', 'full-width', 'sidebar left', 'split-screen')\n"
        "- **width**: The design width in pixels (e.g. 1200, 1440, 375 for mobile)\n"
        "- **colors**: A color palette dict with keys like bg, primary, secondary, text, accent, muted, border, surface\n"
        "- **fonts**: Array of font families used, each with name and sizes used\n"
        "- **sections**: Array of design sections, each with:\n"
        "  - type: Section type (hero, features, footer, header, pricing, testimonials, cta, content, gallery, etc.)\n"
        "  - x, y, w, h: Position and size\n"
        "  - bg: Background color\n"
        "  - columns: Number of columns (1 for single, 2+ for grid)\n"
        "  - elements: Array of visual elements in this section\n"
        "\n"
        "### Element types\n"
        "Each element has: type, text (if any), x, y, w, h, color, bg, font_family, font_size, font_weight, text_align, border_radius, opacity, children\n"
        "Types: heading, paragraph, button, image, icon, card, input, nav, container, divider, list, badge, avatar, progress, chart, table, modal, tabs, accordion, carousel, sidebar, header, footer, hero, section, wrapper\n"
        "\n"
        "### Rules\n"
        "- Be precise with colors — use exact hex values (#rrggbb)\n"
        "- Be precise with dimensions and positions\n"
        "- Extract ALL visible text content exactly as shown\n"
        "- Identify font families, sizes, weights, and alignments from the text\n"
        "- Group elements into sections by visual proximity and purpose\n"
        "- If you see icons or images, mark them as type 'icon' or 'image' with their position and size\n"
        "- Output ONLY valid JSON matching the schema — no markdown, no explanation"
    )

    stage1_payload = {
        "model": vision_model,
        "stream": True,
        "messages": [
            {"role": "system", "content": stage1_system},
            {"role": "user", "content": stage1_prompt},
        ],
        "max_tokens": 2048,
    }

    stage1_result = _call_ai(vision_target, vision_token, vision_model, stage1_payload, "Stage 1")
    if stage1_result is None:
        sys.exit(1)

    # Parse the DesignSpec
    spec_data = _extract_json(stage1_result)
    if spec_data is None:
        print("FAILED: Could not parse Stage 1 response as JSON")
        print("Full response:")
        print(stage1_result)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("STAGE 1 RESULT: Design Spec")
    print("=" * 60)
    print(f"  Layout: {spec_data.get('layout', '(not set)')}")
    print(f"  Width:  {spec_data.get('width', '(not set)')}px")
    print(f"  Colors: {json.dumps(spec_data.get('colors', {}), indent=4)}")
    print(f"  Fonts:  {json.dumps(spec_data.get('fonts', []), indent=4)}")
    sections = spec_data.get("sections", [])
    print(f"  Sections: {len(sections)}")
    for i, s in enumerate(sections):
        print(f"    [{i}] {s.get('type', '?')} ({s.get('w', 0)}x{s.get('h', 0)}) bg={s.get('bg', 'none')} cols={s.get('columns', 1)}")
        for j, e in enumerate(s.get("elements", [])):
            print(f"      [{j}] {e.get('type', '?')} \"{e.get('text', '')[:40]}\" @({e.get('x', 0)},{e.get('y', 0)}) {e.get('w', 0)}x{e.get('h', 0)}")

    # ════════════════════════════════════════════════════════════
    # STAGE 2: Main model → Full Code
    # ════════════════════════════════════════════════════════════
    print("\n" + "=" * 60)
    print("STAGE 2: Main Model → Full Code")
    print("=" * 60)

    # Build the code generation prompt from the spec
    code_prompt_lines = [
        "Generate HTML/CSS/JS code from this design specification.",
        "",
    ]
    if user_prompt:
        code_prompt_lines.append(f"Additional instructions: {user_prompt}")
        code_prompt_lines.append("")

    code_prompt_lines.append(f"Layout: {spec_data.get('layout', 'centered')}")
    code_prompt_lines.append(f"Design width: {spec_data.get('width', 1200)}px")
    code_prompt_lines.append("")

    colors = spec_data.get("colors", {})
    if colors:
        code_prompt_lines.append("## Color Palette")
        for key, val in colors.items():
            code_prompt_lines.append(f"  {key}: {val}")
        code_prompt_lines.append("")

    fonts = spec_data.get("fonts", [])
    if fonts:
        code_prompt_lines.append("## Typography")
        for font in fonts:
            family = font.get("family", "system-ui")
            sizes = font.get("sizes", [])
            if sizes:
                code_prompt_lines.append(f"  {family}: sizes {', '.join(str(s) for s in sizes)}px")
            else:
                code_prompt_lines.append(f"  {family}")
        code_prompt_lines.append("")

    for i, section in enumerate(sections):
        code_prompt_lines.append("")
        code_prompt_lines.append(f"### Section {i+1}: {section.get('type', '?')} ({section.get('w', 0)}x{section.get('h', 0)})")
        if section.get("bg"):
            code_prompt_lines.append(f"  Background: {section['bg']}")
        if section.get("columns", 1) > 1:
            code_prompt_lines.append(f"  Columns: {section['columns']}")
        code_prompt_lines.append("")

        for elem in section.get("elements", []):
            prefix = "  "
            parts = [f"{prefix}[{elem.get('type', '?')}]"]
            if elem.get("text"):
                parts.append(f'"{elem["text"][:60]}"')
            parts.append(f"@({elem.get('x', 0)},{elem.get('y', 0)}) {elem.get('w', 0)}x{elem.get('h', 0)}")
            if elem.get("color"):
                parts.append(f"color:{elem['color']}")
            if elem.get("bg"):
                parts.append(f"bg:{elem['bg']}")
            if elem.get("font_family"):
                parts.append(f"font:{elem['font_family']}")
            if elem.get("font_size"):
                parts.append(f"size:{elem['font_size']}")
            if elem.get("font_weight"):
                parts.append(f"weight:{elem['font_weight']}")
            if elem.get("text_align") and elem.get("text_align") != "left":
                parts.append(f"align:{elem['text_align']}")
            if elem.get("border_radius"):
                parts.append(f"radius:{elem['border_radius']}")
            if elem.get("opacity", 1.0) < 1.0:
                parts.append(f"opacity:{elem['opacity']}")
            code_prompt_lines.append(" ".join(parts))

    code_prompt_lines.append("")
    code_prompt_lines.append("### Requirements")
    code_prompt_lines.append("- Create index.html, style.css, and script.js")
    code_prompt_lines.append("- Use EXACT colors, fonts, dimensions, border-radius from the spec")
    code_prompt_lines.append("- Use modern CSS (flexbox/grid) for layout")
    code_prompt_lines.append("- Make the page responsive")
    code_prompt_lines.append("- Use placeholder SVGs or colored divs for images/icons")
    code_prompt_lines.append("- Center the design in the viewport")
    code_prompt_lines.append("- Every element in the spec must appear in your HTML")

    code_prompt = "\n".join(code_prompt_lines)

    stage2_system = (
        "You are a pixel-perfect frontend developer. Convert the provided design specification into exact HTML/CSS/JS code.\n\n"
        "### Rules\n"
        "- Use exact colors, fonts, dimensions, border-radius, and effects from the spec\n"
        "- Use modern CSS (flexbox/grid) for layout\n"
        "- Make the page responsive where appropriate\n"
        "- Use placeholder SVGs or colored divs for any images/icons in the design\n"
        "- Center the design in the viewport (margin: 0 auto on the main container)\n\n"
        "### Output format\n"
        "Return ONLY valid JSON with \"message\" (string) and \"files\" array. "
        "Each file has \"path\", \"content\", \"file_type\" (html/css/javascript/json/python/other). "
        "Always include index.html, style.css, and script.js."
    )

    stage2_payload = {
        "model": main_model,
        "stream": True,
        "messages": [
            {"role": "system", "content": stage2_system},
            {"role": "user", "content": code_prompt},
        ],
        "max_tokens": 8192,
    }

    stage2_result = _call_ai(main_target, main_token, main_model, stage2_payload, "Stage 2")
    if stage2_result is None:
        sys.exit(1)

    # Parse the final code output
    print("\n" + "=" * 60)
    print("STAGE 2 RESULT: Generated Code")
    print("=" * 60)

    try:
        start = stage2_result.index("{")
        end = stage2_result.rindex("}")
        parsed = json.loads(stage2_result[start : end + 1])
        print(f"Message: {parsed.get('message', '(none)')[:200]}")
        for f in parsed.get("files", []):
            print(f"  {f['path']}: {len(f['content'])} chars")
    except (ValueError, json.JSONDecodeError) as e:
        print(f"Could not parse JSON from response: {e}")
        print("Full response:")
        print(stage2_result)

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
