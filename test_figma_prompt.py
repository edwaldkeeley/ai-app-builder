"""Test the new Figma prompt format with the AI provider."""
import asyncio
import json
import os
import re

import httpx
from dotenv import load_dotenv

load_dotenv()

TARGET_URL = os.getenv("TARGET_URL")
JWT_TOKEN = os.getenv("JWT_TOKEN")
MODEL = os.getenv("MODEL")


async def main():
    headers = {
        "Authorization": f"Bearer {JWT_TOKEN}",
        "Content-Type": "application/json",
    }

    # New format prompt with x/y positions, desktop-only frames, image markers
    figma_prompt = """Design: space-tourism-website

Colors:
  rgb(11,13,23)
  rgb(208,214,249)
  rgb(255,255,255)
  rgb(56,59,75)

Fonts:
  Bellefair | 80.0 | 400
  Barlow Condensed | 16.0 | 400
  Barlow | 15.0 | 400

Sections:
  [0] Desktop - Home - Active [1440.0x900.0px] @(0,0) bg:rgb(11,13,23)
    - Bitmap [1440.0x900.0px] @(0,0) bg:rgb(255,255,255) [IMAGE]
    - Group 16 [450.0x382.0px] @(165.0,258.0) bg:rgb(255,255,255) flex:column justify:center align:flex-start gap:24.0px
    - Group 3 [1385.0x96.0px] @(28.0,0.0) bg:rgb(255,255,255) flex:row justify:space-between align:center
    - Group [450.0x450.0px] @(810.0,225.0) bg:rgb(255,255,255)
    - Rectangle [70.0x3.0px] @(28.0,93.0) bg:rgb(255,255,255)
    - Rectangle Copy [130.0x3.0px] @(28.0,93.0) bg:rgb(255,255,255)
    - Pointer Copy 25 [13.0x14.0px] @(0,0) bg:rgb(255,255,255)
    - Pointer Copy 26 [13.0x14.0px] @(0,0) bg:rgb(255,255,255)

  [1] Desktop - Destination - Active [1440.0x900.0px] @(0,0) bg:rgb(11,13,23)
    - Bitmap [1440.0x900.0px] @(0,0) bg:rgb(255,255,255) [IMAGE]
    - Group 3 [1385.0x96.0px] @(28.0,0.0) bg:rgb(255,255,255) flex:row justify:space-between align:center
    - Group [382.0x34.0px] @(167.0,212.0) bg:rgb(255,255,255)
    - Group 6 [445.0x472.0px] @(890.0,364.0) bg:rgb(255,255,255)
    - Bitmap [445.0x445.0px] @(890.0,391.0) bg:rgb(255,255,255) [IMAGE]
    - Pointer Copy 26 [13.0x14.0px] @(0,0) bg:rgb(255,255,255)

  [2] Desktop - Crew - Active [1440.0x900.0px] @(0,0) bg:rgb(11,13,23)
    - Bitmap [1440.0x900.0px] @(0,0) bg:rgb(255,255,255) [IMAGE]
    - Group 3 [1385.0x96.0px] @(28.0,0.0) bg:rgb(255,255,255) flex:row justify:space-between align:center
    - Group [286.0x34.0px] @(167.0,212.0) bg:rgb(255,255,255)
    - Douglas Hurley [488.0x64.0px] @(167.0,256.0) bg:rgb(255,255,255) text:"Douglas Hurley" font:Bellefair 56.0px color:rgb(255,255,255)
    - Douglas Gerald Hurle [444.0x128.0px] @(167.0,336.0) bg:rgb(208,214,249) text:"Douglas Gerald Hurley is an American engineer, former Marine Corps pilot and former NASA astronaut. ..." font:Barlow 18.0px color:rgb(208,214,249)
    - Group 3 [132.0x15.0px] @(167.0,480.0) bg:rgb(255,255,255)
    - image-removebg-preview(289) [568.1x712.0px] @(705.0,188.0) [IMAGE]
    - Commander [214.0x37.0px] @(167.0,212.0) bg:rgb(255,255,255) text:"Commander " font:Bellefair 32.0px color:rgb(255,255,255)
    - Pointer Copy 26 [13.0x14.0px] @(0,0) bg:rgb(255,255,255)

  [3] Desktop - Technology - Active [1440.0x900.0px] @(0,0) bg:rgb(11,13,23)
    - Bitmap [1440.0x900.0px] @(0,0) bg:rgb(255,255,255) [IMAGE]
    - Group 3 [1385.0x96.0px] @(28.0,0.0) bg:rgb(255,255,255) flex:row justify:space-between align:center
    - Group [305.0x34.0px] @(167.0,212.0) bg:rgb(255,255,255)
    - Group 3 [80.0x80.0px] @(167.0,472.0) bg:rgb(255,255,255)
    - Group 3 Copy [80.0x80.0px] @(247.0,472.0) bg:rgb(255,255,255)
    - Group 3 Copy 2 [80.0x80.0px] @(327.0,472.0) bg:rgb(255,255,255)
    - Bitmap [515.0x527.0px] @(810.0,373.0) bg:rgb(255,255,255) [IMAGE]
    - Group 4 [470.0x303.0px] @(167.0,256.0) bg:rgb(255,255,255)
    - Pointer Copy 26 [13.0x14.0px] @(0,0) bg:rgb(255,255,255)

RULES:
- Create index.html, style.css, script.js
- index.html links style.css and script.js
- Use the EXACT colors from the Colors list above
- Use the EXACT fonts from the Fonts list above
- Each [N] section is a top-level HTML section element
- Indented children with '-' are nested inside their parent
- Use the @(x,y) position data to place elements with CSS position:absolute relative to their parent section
- For elements with flex:row or flex:column, use CSS flexbox instead of absolute
- Match border-radius and dimensions exactly
- [IMAGE] markers mean the node has an image fill — use a colored div or inline SVG as a placeholder
- Do NOT add, remove, or rearrange elements
- Page must look IDENTICAL to the Figma design"""

    system_prompt = """You are a pixel-perfect frontend developer. Your ONLY job is to convert the provided Figma design spec into exact HTML/CSS/JS code. Layout fidelity is your top priority.

CRITICAL RULES:
1. EXACT POSITIONS: Every element has an @(x,y) position. Use CSS position:absolute with left:x and top:y to place elements at their exact coordinates relative to their parent.
2. EXACT DIMENSIONS: Every element has a [WxH] size. Set width and height exactly.
3. EXACT COLORS: Use the exact colors from the Colors list. No substitutions.
4. EXACT TYPOGRAPHY: Use the exact font families, sizes, weights, line heights, letter spacing, and text alignments from the spec.
5. EXACT SPACING: Match padding, gaps, margins, and border radii exactly.
6. EXACT BORDERS: Match border widths, colors, and styles exactly.
7. HIERARCHY: Preserve the parent-child nesting. FRAME nodes with flex:row or flex:column become flexbox containers (use flexbox, not absolute).
8. IMAGES: [IMAGE] markers mean the node has an image fill. Use a colored div or inline SVG as a placeholder. Do NOT use external image URLs.
9. THREE FILES: Create index.html, style.css, and script.js. index.html links to style.css (<link>) and script.js (<script src>). Use semantic HTML5 and modern CSS.
10. NO CREATIVE FREEDOM: Do NOT add, remove, or rearrange elements. Do NOT change colors, fonts, or spacing. Reproduce the design exactly as specified.

HOW TO READ THE FIGMA SPEC:
- Each [N] section is a top-level HTML <section> element
- Indented children with '-' are nested inside their parent
- @(x,y) = position relative to parent (use left:x; top:y; position:absolute)
- [WxH] = width and height in pixels
- bg:color = background color
- [IMAGE] = image placeholder — use a colored div or inline SVG
- text:"content" = text content (use the exact text)
- font:name = font-family
- Npx = font-size
- weight:N = font-weight
- color:color = text color
- align:value = text-align
- lh:Npx = line-height
- ls:N = letter-spacing
- flex:row/column = use CSS flexbox with that direction
- justify:value = justify-content
- align:value = align-items
- gap:Npx = gap
- pad:... = padding
- radius:Npx = border-radius
- border:... = border

OUTPUT FORMAT:
Return ONLY valid JSON. Do NOT wrap the JSON in markdown code blocks.
The JSON must have a "message" field and a "files" array where each file has: "path", "content", "file_type"."""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": figma_prompt},
        ],
        "max_tokens": 16000,
    }

    total_chars = sum(len(m.get("content", "")) for m in payload["messages"])
    print(f"Total prompt: {total_chars} chars (~{total_chars // 3} estimated tokens)")
    print(f"Figma prompt: {len(figma_prompt)} chars")
    print()

    async with httpx.AsyncClient(timeout=180) as client:
        response = await client.post(TARGET_URL, json=payload, headers=headers)

    print(f"Status: {response.status_code}")
    content = response.json()["choices"][0]["message"]["content"]
    print(f"Content length: {len(content)} chars")
    print()

    # Parse JSON
    cleaned = re.sub(r"^```(?:json)?\s*", "", content.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    fb = cleaned.find("{")
    lb = cleaned.rfind("}")
    if fb != -1 and lb != -1:
        cleaned = cleaned[fb : lb + 1]

    try:
        parsed = json.loads(cleaned)
        files = parsed.get("files", [])
        print(f"Files: {len(files)}")
        for f in files:
            print(f'\n=== {f["path"]} ({len(f.get("content", ""))} chars) ===')
            print(f["content"][:2000])
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"First 500: {content[:500]}")
        print(f"Last 500: {content[-500:]}")


if __name__ == "__main__":
    asyncio.run(main())
