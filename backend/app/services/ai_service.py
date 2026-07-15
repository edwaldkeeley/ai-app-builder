"""AI provider abstraction and HTTP implementation.

The ``BaseAIProvider`` abstract class defines the interface for code generation.
``HttpAIProvider`` sends prompts to a configurable ``TARGET_URL`` using JWT
bearer authentication in OpenAI-compatible chat format and parses the response
into project files.

``StreamingHttpAIProvider`` extends this with a streaming variant that yields
events as the response is received, enabling real-time UI updates.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, AsyncIterator

import httpx

from app.config import settings
from app.models.schemas import DesignSpec, FileType, ProjectFile

logger = logging.getLogger(__name__)
# Ensure logger output is visible — uvicorn's log config may not capture app.* loggers
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)


class RateLimitError(RuntimeError):
    """Raised when the AI provider returns a 429 rate-limit response.

    Attributes:
        retry_after: Number of seconds the caller should wait before retrying.
        message: Human-readable description.
    """

    def __init__(self, retry_after: int, message: str | None = None) -> None:
        self.retry_after = retry_after
        if message is None:
            message = f"AI provider rate limited. Retry after {retry_after}s."
        super().__init__(message)


class BaseAIProvider(ABC):
    """Abstract interface for AI code generation."""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
    ) -> tuple[str, list[ProjectFile]]:
        """Send a prompt and return (message, list of project files).

        Args:
            prompt: The latest user prompt.
            existing_files: Current files in the project (for context).
            chat_history: Previous conversation messages.
            system_prompt_override: Optional system prompt to use instead of the default.
                Used for Figma imports where layout fidelity is critical.
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream generation events.

        Args:
            prompt: The latest user prompt.
            existing_files: Current files in the project (for context).
            chat_history: Previous conversation messages.
            system_prompt_override: Optional system prompt to use instead of the default.

        Yields dicts with a ``type`` key:
        - ``{"type": "message_chunk", "delta": "..."}`` — partial message text
        - ``{"type": "file_start", "path": "...", "file_type": "..."}`` — new file
        - ``{"type": "file_chunk", "path": "...", "delta": "..."}`` — partial file content
        - ``{"type": "file_done", "path": "..."}`` — file complete
        - ``{"type": "done", "message": "...", "files": [...]}`` — generation complete
        """
        ...

    @abstractmethod
    async def analyze_design(
        self,
        image_data_uri: str,
        filename: str = "design",
        mime_type: str = "image/png",
    ) -> str:
        """Stage 1: Analyze a design image and return a detailed text description.

        Args:
            image_data_uri: Base64-encoded data URI of the design image.
            filename: Original filename for context.
            mime_type: MIME type of the image.

        Returns:
            A detailed natural-language description of the design.
        """
        ...

    @abstractmethod
    async def generate_from_spec(
        self,
        design_description: str,
        user_prompt: str = "",
    ) -> tuple[str, list[ProjectFile]]:
        """Stage 2: Generate full HTML/CSS/JS code from a design description.

        Args:
            design_description: The text description from analyze_design().
            user_prompt: Optional additional instructions from the user.

        Returns:
            (message, list of ProjectFile) from the AI provider.
        """
        ...


_SYSTEM_PROMPT = (
    "You are a Full-Stack Software Engineer and a brilliant Product Designer. "
    "Your goal is to build fully functional, production-ready web applications based on user descriptions.\n\n"
    "You will receive the conversation history and the current list of project files. "
    "Your job is to respond to the latest user request by modifying, adding, or deleting files as needed.\n\n"
    "GUIDELINES:\n"
    "1. Analyze First: Before writing any code, think through the user personas, core data models, "
    "and main user flows. Consider business logic, edge cases, and design preferences.\n"
    "2. Architecture: Use modern, clean, and secure frameworks. Default to vanilla HTML/CSS/JS "
    "unless the user specifies a framework.\n"
    "3. Modularity: Keep code clean, well-organized, and properly commented.\n"
    "4. Error Handling: Include graceful error handling, loading states, and form validations.\n"
    "5. Design: Make it look professional — use proper spacing, typography, color schemes, "
    "and responsive layouts. Think like a product designer.\n\n"
    "OUTPUT FORMAT:\n"
    "Return ONLY valid JSON. Do NOT wrap the JSON in markdown code blocks.\n"
    'The JSON must have a "message" field (string, explain what you built in a friendly conversational tone) '
    'and a "files" array where each file has: '
    '"path" (string), "content" (string), "file_type" (one of: html, css, javascript, json, python, other).\n\n'
    "CONVERSATION RULES:\n"
    "6. Only include files you want to CREATE or MODIFY. Files you don't include will be left unchanged by the system. "
    "Do NOT echo back files that haven't changed.\n"
    "7. If the user asks to modify something specific (e.g. 'add a chart', 'fix the layout'), only include the changed files. "
    "Do NOT regenerate the entire project.\n"
    "8. If the user asks to delete a file, omit it from the files array (the system will handle deletion).\n"
    "9. Preserve proper indentation and line breaks in file content.\n"
    "10. Use standard filenames (index.html, style.css, script.js, app.js, etc.).\n\n"
    "BUG FIXING RULES:\n"
    "11. When the user reports a bug, first identify the root cause by reading the relevant file content. "
    "Then output the FULL corrected file — never output only the changed lines or a diff.\n"
    "12. Be thorough: check for common issues like missing imports, incorrect selectors, "
    "unclosed tags, mismatched brackets, wrong API endpoints, and CSS specificity problems.\n"
    "13. If a fix requires changes to multiple files, include ALL of them in the files array "
    "with their COMPLETE updated content.\n"
    "14. After fixing, explain in the 'message' field what the bug was and how you fixed it."
)

_DESIGN_UPLOAD_SYSTEM_PROMPT = (
    "You are a pixel-perfect frontend developer. Convert the provided design image into exact HTML/CSS/JS code.\n\n"
    "### Rules\n"
    "- Analyze the image carefully for layout, colors, typography, spacing, and visual hierarchy\n"
    "- Reproduce the design as accurately as possible using HTML, CSS, and JavaScript\n"
    "- Use exact colors, fonts (use system fonts or Google Fonts), dimensions, border-radius, and effects\n"
    "- Use modern CSS (flexbox/grid) for layout\n"
    "- Make the page responsive where appropriate\n"
    "- Use placeholder SVGs or colored divs for any images/icons in the design\n"
    "- Center the design in the viewport (margin: 0 auto on the main container)\n\n"
    "### Output format\n"
    "Return ONLY valid JSON with \"message\" (string) and \"files\" array. "
    "Each file has \"path\", \"content\", \"file_type\" (html/css/javascript/json/python/other). "
    "Always include index.html, style.css, and script.js."
)

_DESIGN_ANALYSIS_PROMPT = (
    "You are a design analyzer. Your job is to look at the provided design image and describe "
    "it in DETAILED plain text. Do NOT write any code. Do NOT output JSON.\n\n"
    "Describe the design thoroughly, covering:\n\n"
    "### 1. Overall Layout\n"
    "- Layout type (centered single column, full-width, sidebar, split-screen, etc.)\n"
    "- Design width in pixels\n"
    "- How content is arranged (stacked, grid, overlapping, etc.)\n\n"
    "### 2. Color Palette\n"
    "- List EVERY distinct color you see with its exact hex value (#rrggbb)\n"
    "- Describe where each color is used (background, text, buttons, borders, etc.)\n\n"
    "### 3. Typography\n"
    "- Font families used (serif, sans-serif, specific names if identifiable)\n"
    "- Font sizes, weights, and styles for each text element\n"
    "- Text alignment and colors\n\n"
    "### 4. Sections (describe each one in order from top to bottom)\n"
    "For each section:\n"
    "- Section type/name (header, hero, features, pricing, footer, etc.)\n"
    "- Background color and dimensions\n"
    "- Number of columns if a grid layout\n"
    "- Every element inside: type (heading, paragraph, button, image, icon, card, input, nav link, etc.), "
    "exact text content, position, size, colors, font details, border-radius\n"
    "- For buttons: text, colors, size, border-radius, hover state if visible\n"
    "- For images/icons: position, size, shape, color\n"
    "- For navigation: list all links with their text and position\n\n"
    "### Rules\n"
    "- Be EXTREMELY precise with colors — use exact hex values\n"
    "- Be precise with dimensions and positions\n"
    "- Extract ALL visible text content exactly as shown — every heading, paragraph, button label, link\n"
    "- Note any visual effects: shadows, gradients, borders, opacity\n"
    "- Describe the visual hierarchy: what stands out most, what's secondary\n"
    "- If the design has multiple pages or states, describe each one"
)

_FIGMA_SYSTEM_PROMPT = (
    "You are a pixel-perfect frontend developer. Convert the provided Figma design into exact HTML/CSS/JS code.\n\n"
    "The design has two parts:\n"
    "1. **Design Tree Summary** — every node with type, position, size, colors, text. PRIMARY reference.\n"
    "2. **Filtered Figma JSON** — additional detail if needed.\n\n"
    "### Multi-canvas handling\n"
    "If all canvases are the same viewport type (e.g. all desktop width), they are DIFFERENT PAGES. "
    "Generate ONE HTML file with all pages. "
    "Use your judgment: stack vertically for scrolling, or use JS section switching if there's a nav bar. "
    "If canvases have DIFFERENT viewport types (desktop + mobile), generate ONE responsive page with CSS media queries.\n\n"
    "### Rules\n"
    "- Every node in the summary must appear in your HTML — do not skip any\n"
    "- Use exact colors, fonts, dimensions, border-radius, and effects from the summary\n"
    "- Use position:absolute with left/top for positioned elements\n"
    "- Use flexbox for FRAME nodes with layoutMode (HORIZONTAL/VERTICAL)\n"
    "- Use colored divs or SVG for images (no external URLs)\n"
    "- Do NOT add, remove, or rearrange elements\n"
    "- Center the design in the viewport (margin: 0 auto on the main container)\n\n"
    "### Output format\n"
    "Return ONLY valid JSON with \"message\" (string) and \"files\" array. "
    "Each file has \"path\", \"content\", \"file_type\" (html/css/javascript/json/python/other). "
    "Always include index.html, style.css, and script.js."
)


def _parse_retry_after(response: httpx.Response, default: int = 10) -> int:
    """Parse the Retry-After header from a 429 response.

    Handles both integer seconds (``Retry-After: 120``) and HTTP-date
    (``Retry-After: Fri, 31 Dec 2021 23:59:59 GMT``) formats per RFC 7231.

    Falls back to the response body's ``retry_after`` / ``Retry-After`` fields,
    then to the provided ``default``.
    Capped at 120 seconds to avoid bogus values.
    """
    header = response.headers.get("Retry-After")
    if header:
        # Try integer seconds first
        try:
            return min(int(header), 120)
        except ValueError:
            pass
        # Try HTTP-date format
        try:
            parsed = datetime.strptime(header, "%a, %d %b %Y %H:%M:%S %Z")
            now = datetime.now(timezone.utc)
            wait = (parsed.replace(tzinfo=timezone.utc) - now).total_seconds()
            if wait > 0:
                return min(int(wait), 120)
        except ValueError:
            pass
    # Try to parse from response body
    try:
        body = response.json()
        val = body.get("retry_after", body.get("Retry-After", default))
        return min(int(val), 120)
    except Exception:
        return default


def _build_payload(
    prompt: str,
    existing_files: list[ProjectFile] | None = None,
    chat_history: list[dict[str, str]] | None = None,
    system_prompt_override: str | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Build the OpenAI-compatible messages payload.

    Args:
        prompt: The latest user prompt.
        existing_files: Current files in the project (sent as context).
        chat_history: Previous messages in the conversation.
        system_prompt_override: Optional system prompt to use instead of the default.
        max_tokens: Maximum output tokens for the AI response.
    """
    system_prompt = system_prompt_override if system_prompt_override else _SYSTEM_PROMPT
    messages: list[dict[str, str]] = [
        {"role": "system", "content": system_prompt},
    ]

    # Include existing file list with full content as context
    if existing_files:
        file_sections = []
        for f in existing_files:
            file_sections.append(
                f"--- {f.path} ({f.file_type.value}) ---\n{f.content}"
            )
        messages.append({
            "role": "system",
            "content": "Current project files (with full contents):\n\n" + "\n\n".join(file_sections),
        })

    # Include conversation history (limited to prevent context overflow)
    if chat_history:
        # Keep only the last 10 messages to bound context growth
        MAX_HISTORY_MESSAGES = 10
        # Truncate individual message content to 2000 chars to save context
        MAX_MESSAGE_LENGTH = 2000
        recent_history = chat_history[-MAX_HISTORY_MESSAGES:]
        for msg in recent_history:
            truncated = {**msg}
            if isinstance(truncated.get("content"), str) and len(truncated["content"]) > MAX_MESSAGE_LENGTH:
                truncated["content"] = truncated["content"][:MAX_MESSAGE_LENGTH] + "\n\n[content truncated]"
            messages.append(truncated)

    # Add the latest user prompt
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "messages": messages,
        "model": None,  # set by the provider
    }
    if max_tokens is not None and max_tokens > 0:
        payload["max_tokens"] = max_tokens
    # else: omit max_tokens entirely — let the provider use its default

    # Warn if prompt is approaching common context window limits
    total_chars = sum(len(m.get("content", "")) for m in messages)
    estimated_input_tokens = total_chars // 3
    if estimated_input_tokens > 100_000:
        logger.warning(
            "Prompt is very large: ~%d estimated input tokens (%.1f MB). "
            "This may exceed the model's context window.",
            estimated_input_tokens, total_chars / 1024 / 1024,
        )
    elif estimated_input_tokens > 50_000:
        logger.info(
            "Prompt is large: ~%d estimated input tokens. "
            "Consider reducing prompt size if quality degrades.",
            estimated_input_tokens,
        )

    return payload


def _extract_code_blocks(content: str) -> list[tuple[str, str]]:
    """Extract code blocks with their language from markdown.

    Returns list of (language, code) tuples, e.g. ("html", "<!DOCTYPE...>").
    """
    pattern = re.compile(r"```(\w+)?\s*\n(.*?)```", re.DOTALL)
    blocks = []
    for match in pattern.finditer(content):
        lang = (match.group(1) or "").lower()
        code = match.group(2).strip()
        if code:
            blocks.append((lang, code))
    return blocks


def _code_blocks_to_files(
    raw_content: str,
    blocks: list[tuple[str, str]],
    existing_files: list[ProjectFile] | None = None,
) -> tuple[str, list[ProjectFile]]:
    """Convert markdown code blocks into ProjectFiles.

    Maps language tags to filenames: html→index.html, css→style.css,
    js/javascript→script.js. Any text before the first code block is
    treated as the conversational message.
    """
    # Text before the first code block is the message
    message = raw_content.strip()
    first_block = raw_content.find("```")
    if first_block > 0:
        message = raw_content[:first_block].strip()
    elif first_block == 0:
        message = ""

    lang_to_path = {
        "html": "index.html",
        "css": "style.css",
        "js": "script.js",
        "javascript": "script.js",
    }
    lang_to_type = {
        "html": FileType.html,
        "css": FileType.css,
        "js": FileType.js,
        "javascript": FileType.js,
    }

    ai_files: list[ProjectFile] = []
    for lang, code in blocks:
        path = lang_to_path.get(lang)
        file_type = lang_to_type.get(lang, FileType.other)
        if path is None:
            # Unknown language — skip or treat as other
            path = f"file.{lang}" if lang else "file.txt"
            file_type = FileType.other
        ai_files.append(ProjectFile(path=path, content=code, file_type=file_type))

    # Merge with existing files (AI files override)
    merged_map: dict[str, ProjectFile] = {}
    if existing_files:
        for ef in existing_files:
            merged_map[ef.path] = ef
    for f in ai_files:
        merged_map[f.path] = f

    return message, list(merged_map.values())


def _parse_final_json(
    content: str,
    existing_files: list[ProjectFile] | None = None,
) -> tuple[str, list[ProjectFile]]:
    """Parse the final JSON response into (message, files).

    First attempts JSON parsing. If that fails (e.g. the model returned
    markdown code blocks instead of JSON), falls back to extracting
    HTML/CSS/JS from markdown code blocks.

    Merges AI output with existing files: only files the AI explicitly returns
    are updated; all other existing files are preserved unchanged.
    """
    # Strip markdown code block if present — only if the ENTIRE content
    # is a single code block (starts and ends with ```). Otherwise the
    # regex would strip the last ``` from multi-block content, breaking
    # the last block's closing fence.
    stripped = content.strip()
    if stripped.startswith("```") and stripped.rstrip().endswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", stripped)
        content = re.sub(r"\s*```$", "", content)
    else:
        content = stripped

    # Find the first '{' and last '}' to extract JSON robustly
    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = content[first_brace : last_brace + 1]
    else:
        json_candidate = content

    try:
        parsed = json.loads(json_candidate)
    except json.JSONDecodeError:
        # Fallback: extract code blocks from markdown
        logger.warning("JSON parsing failed, falling back to markdown code block extraction")
        blocks = _extract_code_blocks(content)
        if blocks:
            return _code_blocks_to_files(content, blocks, existing_files)
        raise
    except json.JSONDecodeError:
        # Fallback: extract code blocks from markdown
        logger.warning("JSON parsing failed, falling back to markdown code block extraction")
        blocks = _extract_code_blocks(content)
        if blocks:
            return _code_blocks_to_files(content, blocks, existing_files)
        raise

    raw_files = parsed.get("files", [])
    message = parsed.get("message", "")

    # Build merged file list: AI files override existing files by path
    ai_files_map: dict[str, ProjectFile] = {}
    for f in raw_files:
        # Handle unknown file_type gracefully — default to "other"
        raw_type = f.get("file_type", "other")
        try:
            file_type = FileType(raw_type)
        except ValueError:
            file_type = FileType.other

        ai_files_map[f["path"]] = ProjectFile(
            path=f["path"],
            content=f.get("content", ""),
            file_type=file_type,
        )

    # Start with existing files, then overlay AI changes
    merged_map: dict[str, ProjectFile] = {}
    if existing_files:
        for ef in existing_files:
            merged_map[ef.path] = ef

    # AI files override existing ones
    merged_map.update(ai_files_map)

    merged_files = list(merged_map.values())

    return message, merged_files


def _validate_generated_files(
    files: list[ProjectFile],
    design_name: str = "",
) -> list[str]:
    """Validate generated files for common issues.

    Checks:
    - index.html exists
    - style.css exists
    - script.js exists
    - index.html links to style.css
    - index.html links to script.js
    - style.css has content (not empty)
    - index.html has a <body> tag
    - index.html has a <title> tag

    Returns a list of warning messages (empty = no issues).
    """
    warnings: list[str] = []
    file_map = {f.path: f for f in files}

    # Check all three required files exist
    for required in ["index.html", "style.css", "script.js"]:
        if required not in file_map:
            warnings.append(f"Missing required file: {required}")

    # Validate index.html structure
    if "index.html" in file_map:
        html_content = file_map["index.html"].content
        if "style.css" not in html_content and '<link rel="stylesheet"' not in html_content:
            warnings.append("index.html does not link to style.css")
        if "script.js" not in html_content and '<script' not in html_content:
            warnings.append("index.html does not link to script.js")
        if "<body" not in html_content:
            warnings.append("index.html is missing <body> tag")
        if "<title>" not in html_content:
            warnings.append("index.html is missing <title> tag")

    # Validate style.css has content
    if "style.css" in file_map:
        css_content = file_map["style.css"].content.strip()
        if not css_content:
            warnings.append("style.css is empty")
        elif len(css_content) < 50:
            warnings.append(f"style.css seems too short ({len(css_content)} chars)")

    # Validate script.js has content
    if "script.js" in file_map:
        js_content = file_map["script.js"].content.strip()
        if not js_content:
            warnings.append("script.js is empty")

    return warnings


def _repair_json(content: str) -> str:
    """Attempt to repair common JSON issues from LLM output.

    Handles:
    - Single quotes instead of double quotes
    - Trailing commas before ``]`` or ``}``
    - Missing commas between key-value pairs or array elements
    - Unquoted string values (e.g. ``true``, ``null`` — these are valid JSON)
    """
    # Replace single quotes with double quotes FIRST so all subsequent regexes
    # can rely on double-quote patterns
    content = content.replace("'", '"')

    # Strip trailing commas before ] or }
    content = re.sub(r",\s*([}\]])", r"\1", content)

    # Insert missing commas: a closing quote followed by whitespace then an opening
    # quote, but NOT separated by a colon (which would be a key:value pair).
    # Pattern: "value" "key" → "value", "key"  (missing comma between array elements
    # or between one value and the next key)
    content = re.sub(r'"\s+"', r'", "', content)

    # Insert missing commas: } followed by " (end of object then next key)
    content = re.sub(r'}\s*"', r'}, "', content)

    # Insert missing commas: } followed by { (end of object then next object in array)
    content = re.sub(r'}\s*\{', r'}, {', content)

    # Insert missing commas: ] followed by " (end of array then next key)
    content = re.sub(r']\s*"', r'], "', content)

    # Insert missing commas: digit/true/false/null followed by " (value then next key)
    content = re.sub(r'(\d|true|false|null)\s+"', r'\1, "', content)

    # Insert missing commas: " followed by { (key then nested object value)
    content = re.sub(r'"\s*\{', r'", {', content)

    return content


def _try_parse_json(content: str) -> dict | None:
    """Try multiple strategies to parse JSON from LLM output.

    Returns the parsed dict on success, or ``None`` if all strategies fail.
    """
    strategies = [
        ("basic trailing comma fix", lambda c: re.sub(r",\s*([}\]])", r"\1", c)),
        ("comprehensive repair", _repair_json),
    ]

    for name, fixer in strategies:
        try:
            fixed = fixer(content)
            return json.loads(fixed)
        except json.JSONDecodeError as e:
            logger.debug("Strategy '%s' failed at line %d col %d: %s",
                          name, e.lineno, e.colno, e.msg)
            continue

    # Last resort: try ast.literal_eval after converting JSON literals to Python
    try:
        import ast
        py_content = content
        py_content = py_content.replace("true", "True")
        py_content = py_content.replace("false", "False")
        py_content = py_content.replace("null", "None")
        result = ast.literal_eval(py_content)
        if isinstance(result, dict):
            return result
    except (SyntaxError, ValueError) as e:
        logger.debug("ast.literal_eval failed: %s", e)

    # Absolute last resort: use raw_decode to find the first valid JSON object.
    # This handles cases where the model appends extra text after valid JSON.
    try:
        decoder = json.JSONDecoder()
        for fixer_name, fixer in strategies:
            fixed = fixer(content)
            try:
                obj, _ = decoder.raw_decode(fixed)
                if isinstance(obj, dict):
                    logger.debug("raw_decode succeeded after '%s'", fixer_name)
                    return obj
            except json.JSONDecodeError:
                continue
    except Exception:
        pass

    return None


def _coerce_design_spec_types(obj: Any) -> Any:
    """Coerce string values to their expected numeric types in a DesignSpec dict.

    The vision model often outputs string values like ``"24px"``, ``"700"``,
    ``"bold"``, ``"1"`` for fields that should be ``int`` or ``float``.
    This walks the parsed dict and converts values to appropriate types.
    """
    if isinstance(obj, dict):
        numeric_int_fields = {"x", "y", "w", "h", "font_size", "font_weight",
                              "border_radius", "columns", "width"}
        numeric_float_fields = {"opacity"}

        for key, value in obj.items():
            if isinstance(value, str):
                # Strip px, %, em, rem suffixes for size/dimension fields
                if key in numeric_int_fields:
                    cleaned = value.lower().replace("px", "").replace("%", "").replace("em", "").replace("rem", "")
                    try:
                        obj[key] = int(float(cleaned))
                    except (ValueError, TypeError):
                        pass  # Keep original string if conversion fails
                elif key in numeric_float_fields:
                    try:
                        obj[key] = float(value)
                    except (ValueError, TypeError):
                        pass
                elif key == "font_weight":
                    # Map common font-weight keywords to numeric values
                    weight_map = {
                        "thin": 100, "extralight": 200, "light": 300,
                        "normal": 400, "regular": 400,
                        "medium": 500, "semibold": 600, "bold": 700,
                        "extrabold": 800, "black": 900,
                    }
                    lower = value.lower().strip()
                    if lower in weight_map:
                        obj[key] = weight_map[lower]
            elif isinstance(value, list):
                obj[key] = [_coerce_design_spec_types(item) for item in value]
            elif isinstance(value, dict):
                obj[key] = _coerce_design_spec_types(value)

    elif isinstance(obj, list):
        return [_coerce_design_spec_types(item) for item in obj]

    return obj


def _parse_design_spec_response(content: str) -> DesignSpec:
    """Parse the vision model's JSON response into a DesignSpec.

    Handles markdown-wrapped JSON, trailing commas, missing commas, and other
    common LLM JSON issues. Extracts the first JSON object robustly.
    """
    # Strip markdown code block if present
    content = re.sub(r"^```(?:json)?\s*", "", content.strip())
    content = re.sub(r"\s*```$", "", content)

    # Find the first '{' and last '}' to extract JSON robustly
    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        content = content[first_brace : last_brace + 1]

    parsed = _try_parse_json(content)
    if parsed is None:
        logger.error(
            "All JSON parsing strategies failed for design spec. "
            "Full content: %s", content,
        )
        raise ValueError("Failed to parse design spec JSON after all repair attempts")

    # Coerce string values to expected numeric types (vision model often
    # outputs "24px", "700", "bold" instead of 24, 700, etc.)
    parsed = _coerce_design_spec_types(parsed)

    # Convert raw dicts to DesignSpec (handles nested DesignElement/DesignSection)
    return DesignSpec.model_validate(parsed)


def _build_design_code_prompt(design_description: str, user_prompt: str = "") -> str:
    """Build a prompt for the main code generation model from a design description.

    Args:
        design_description: The text description from Stage 1 (vision model analysis).
        user_prompt: Optional additional instructions from the user.

    Returns:
        A prompt string for the main AI provider.
    """
    lines: list[str] = []
    lines.append("Generate HTML/CSS/JS code from this design description.")
    lines.append("")
    if user_prompt:
        lines.append(f"Additional instructions: {user_prompt}")
        lines.append("")
    lines.append("=" * 60)
    lines.append("DESIGN DESCRIPTION")
    lines.append("=" * 60)
    lines.append(design_description)
    lines.append("")
    lines.append("=" * 60)
    lines.append("REQUIREMENTS")
    lines.append("=" * 60)
    lines.append("- Create index.html, style.css, and script.js")
    lines.append("- Use EXACT colors, fonts, dimensions, border-radius from the description")
    lines.append("- Use modern CSS (flexbox/grid) for layout")
    lines.append("- Make the page responsive")
    lines.append("- Use placeholder SVGs or colored divs for images/icons")
    lines.append("- Center the design in the viewport")
    lines.append("- Every element described must appear in your HTML")
    lines.append("- Match the visual hierarchy: primary headings should be largest, then secondary, etc.")
    lines.append("- Use proper semantic HTML elements (<header>, <nav>, <main>, <section>, <footer>)")
    lines.append("- Include hover effects on buttons and links where described")

    return "\n".join(lines)

    return "\n".join(lines)


def _format_element_for_prompt(lines: list[str], elem: DesignSpec | None = None, indent: int = 0, **kwargs) -> None:
    """Format a design element for the prompt."""
    # Handle both DesignElement objects and raw dicts
    if elem is not None:
        pass  # use elem
    elif "element" in kwargs:
        elem = kwargs["element"]
    else:
        return

    prefix = "  " * indent
    parts = [f"{prefix}[{elem.type}]"]
    if elem.text:
        parts.append(f'"{elem.text[:60]}"')
    parts.append(f"@({elem.x},{elem.y}) {elem.w}x{elem.h}")
    if elem.color:
        parts.append(f"color:{elem.color}")
    if elem.bg:
        parts.append(f"bg:{elem.bg}")
    if elem.font_family:
        parts.append(f"font:{elem.font_family}")
    if elem.font_size:
        parts.append(f"size:{elem.font_size}")
    if elem.font_weight:
        parts.append(f"weight:{elem.font_weight}")
    if elem.text_align and elem.text_align != "left":
        parts.append(f"align:{elem.text_align}")
    if elem.border_radius:
        parts.append(f"radius:{elem.border_radius}")
    if elem.opacity < 1.0:
        parts.append(f"opacity:{elem.opacity}")
    lines.append(" ".join(parts))

    for child in elem.children:
        _format_element_for_prompt(lines, child, indent + 1)


class HttpAIProvider(BaseAIProvider):
    """AI provider that calls a remote HTTP endpoint.

    Sends prompts in OpenAI-compatible chat format and expects a response
    with a JSON ``files`` array embedded in ``choices[0].message.content``::

        {
          "choices": [{
            "message": {
              "content": "{\\"files\\": [{\\"path\\": \\"...\\", \\"content\\": \\"...\\", \\"file_type\\": \\"html\\"}]}"
            }
          }]
        }
    """

    def __init__(
        self,
        target_url: str,
        jwt_token: str,
        model: str,
        timeout: float = 300.0,
    ) -> None:
        self._target_url = target_url
        self._jwt_token = jwt_token
        self._model = model
        self._timeout = timeout
        self._connect_timeout = 30.0  # separate connect timeout to avoid proxy timeouts

    async def generate(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
    ) -> tuple[str, list[ProjectFile]]:
        headers = {
            "Authorization": f"Bearer {self._jwt_token}",
            "Content-Type": "application/json",
        }

        payload = _build_payload(prompt, existing_files, chat_history, system_prompt_override, max_tokens=settings.max_tokens)
        payload["model"] = self._model

        # Log prompt size for debugging
        total_chars = sum(len(m.get("content", "")) for m in payload.get("messages", []))
        total_messages = len(payload.get("messages", []))
        # Rough token estimate: ~4 chars per token for English text + JSON
        estimated_tokens = total_chars // 3
        max_tokens_val = payload.get("max_tokens", "default")
        logger.info(
            "AI generate prompt: %d messages, %d chars, ~%d estimated tokens, max_tokens=%s",
            total_messages, total_chars, estimated_tokens, max_tokens_val,
        )
        # Log the system prompt and user prompt
        for i, msg in enumerate(payload.get("messages", [])):
            role = msg.get("role", "?")
            content_preview = msg.get("content", "")[:300]
            logger.info("  Message[%d] role=%s: %s...", i, role, content_preview)

        max_retries = 3
        response: httpx.Response | None = None
        for attempt in range(max_retries + 1):
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout, connect=self._connect_timeout)) as client:
                response = await client.post(self._target_url, json=payload, headers=headers)

            if response.status_code == 401:
                raise RuntimeError("AI provider authentication failed (401). Check your JWT_TOKEN.")
            if response.status_code == 404:
                raise RuntimeError(f"AI provider endpoint not found (404). Check your TARGET_URL.")
            if response.status_code == 429:
                wait = _parse_retry_after(response)
                if attempt >= max_retries:
                    raise RateLimitError(
                        retry_after=wait,
                        message=f"AI provider rate limited (429). Retry after {wait}s. Max retries ({max_retries}) exceeded.",
                    )
                logger.warning("AI provider rate limited (429). Retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
                continue
            if not response.is_success:
                raise RuntimeError(
                    f"AI provider returned {response.status_code}: {response.text[:500]}"
                )

            # Success — break out of retry loop
            break

        assert response is not None  # guaranteed by the loop above
        data: dict[str, Any] = response.json()

        # Log the raw response for debugging
        logger.info("AI response status: %d", response.status_code)
        logger.info("AI response data (first 500 chars): %s", str(data)[:500])

        # Extract content from OpenAI-compatible response
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(
                f"Unexpected AI response format. Expected 'choices[0].message.content'. Got: {str(data)[:300]}"
            ) from e

        if not content or not content.strip():
            logger.error("AI provider returned empty content. Full response: %s", str(data)[:500])
            raise RuntimeError(
                "AI provider returned an empty response. "
                "The prompt may be too large for the model's context window, "
                "or the model failed to generate a response."
            )

        logger.info("AI response content (first 500 chars): %s", content[:500])
        logger.info("AI response content length: %d chars", len(content))

        message, files = _parse_final_json(content, existing_files)

        # Validate generated files and log warnings
        warnings = _validate_generated_files(files)
        if warnings:
            logger.warning("Generated file validation warnings (%d):", len(warnings))
            for w in warnings:
                logger.warning("  - %s", w)
            # Append warnings to the message so the frontend can display them
            if warnings:
                message += "\n\n**Note:** " + " ".join(warnings)

        return message, files

    async def generate_stream(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Non-streaming fallback — yields the complete result as a single event."""
        message, files = await self.generate(prompt, existing_files, chat_history, system_prompt_override)
        for f in files:
            yield {"type": "file_start", "path": f.path, "file_type": f.file_type.value}
            yield {"type": "file_chunk", "path": f.path, "delta": f.content}
            yield {"type": "file_done", "path": f.path}
        yield {"type": "done", "message": message, "files": [f.model_dump() for f in files]}

    async def analyze_design(
        self,
        image_data_uri: str,
        filename: str = "design",
        mime_type: str = "image/png",
    ) -> str:
        """Stage 1: Analyze a design image and return a detailed text description.

        Sends the image to the vision model with a detailed analysis prompt.
        The model returns a rich natural-language description of the design
        (not code, not JSON).

        Note: This provider (qwen2.5-vl-7b) only supports SSE streaming responses,
        so we read the event stream and collect the full text.
        """
        headers = {
            "Authorization": f"Bearer {self._jwt_token}",
            "Content-Type": "application/json",
        }

        prompt = (
            f"Describe this design image in detail.\n"
            f"Filename: {filename}\n"
            f"Type: {mime_type}\n"
            f"Image (data URI):\n{image_data_uri}"
        )

        payload = _build_payload(
            prompt,
            system_prompt_override=_DESIGN_ANALYSIS_PROMPT,
            max_tokens=2048,  # keep output small to fit 8k context window
        )
        payload["model"] = self._model
        payload["stream"] = True  # this provider only supports SSE streaming

        logger.info("Design analysis request: %s, model=%s", filename, self._model)

        max_retries = 2
        for attempt in range(max_retries + 1):
            async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout, connect=self._connect_timeout)) as client:
                async with client.stream("POST", self._target_url, json=payload, headers=headers) as response:

                    if response.status_code == 429:
                        wait = _parse_retry_after(response)
                        if attempt >= max_retries:
                            raise RateLimitError(
                                retry_after=wait,
                                message=f"AI provider rate limited (429). Retry after {wait}s.",
                            )
                        logger.warning("Rate limited (429). Retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                        await asyncio.sleep(wait)
                        continue
                    if not response.is_success:
                        raise RuntimeError(
                            f"AI provider returned {response.status_code}: {response.text[:500]}"
                        )

                    # Read the SSE stream and collect the full content
                    full_content = ""
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk.get("choices", [{}])[0].get("delta", {})
                                text = delta.get("content", "")
                                if text:
                                    full_content += text
                            except json.JSONDecodeError:
                                continue

                    if not full_content or not full_content.strip():
                        raise RuntimeError("AI provider returned empty response for design analysis.")

                    logger.info("Design analysis response: %d chars", len(full_content))
                    return full_content.strip()

    async def generate_from_spec(
        self,
        design_description: str,
        user_prompt: str = "",
    ) -> tuple[str, list[ProjectFile]]:
        """Stage 2: Generate full HTML/CSS/JS code from a design description.

        Takes the text description from Stage 1 (vision model analysis) and
        feeds it into the main code generation model.
        """
        code_prompt = _build_design_code_prompt(design_description, user_prompt)
        return await self.generate(
            code_prompt,
            system_prompt_override=_DESIGN_UPLOAD_SYSTEM_PROMPT,
        )


class StreamingHttpAIProvider(BaseAIProvider):
    """AI provider that streams responses from an OpenAI-compatible endpoint.

    Uses ``stream: true`` to receive SSE chunks. Message text is extracted from
    the streaming JSON and yielded character-by-character. File definitions are
    parsed from the complete JSON after the stream ends.
    """

    def __init__(
        self,
        target_url: str,
        jwt_token: str,
        model: str,
        timeout: float = 300.0,
    ) -> None:
        self._target_url = target_url
        self._jwt_token = jwt_token
        self._model = model
        self._timeout = timeout
        self._connect_timeout = 30.0  # separate connect timeout to avoid proxy timeouts

    async def generate(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
    ) -> tuple[str, list[ProjectFile]]:
        """Non-streaming fallback — delegates to HttpAIProvider logic."""
        provider = HttpAIProvider(
            self._target_url, self._jwt_token, self._model, self._timeout
        )
        return await provider.generate(prompt, existing_files, chat_history, system_prompt_override)

    async def generate_stream(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self._jwt_token}",
            "Content-Type": "application/json",
        }

        payload = _build_payload(prompt, existing_files, chat_history, system_prompt_override, max_tokens=settings.max_tokens)
        payload["model"] = self._model
        payload["stream"] = True

        # Log prompt size for debugging
        total_chars = sum(len(m.get("content", "")) for m in payload.get("messages", []))
        total_messages = len(payload.get("messages", []))
        estimated_tokens = total_chars // 3
        max_tokens_val = payload.get("max_tokens", "default")
        logger.info(
            "AI generate_stream prompt: %d messages, %d chars, ~%d estimated tokens, max_tokens=%s",
            total_messages, total_chars, estimated_tokens, max_tokens_val,
        )

        accumulated_content = ""
        prev_message = ""
        # Track files we've already announced so we don't repeat
        announced_files: set[str] = set()
        # Track file content we've already streamed
        streamed_file_content: dict[str, str] = {}
        # Pre-populate announced_files with existing files (they're preserved, not streamed)
        if existing_files:
            for ef in existing_files:
                announced_files.add(ef.path)

        # Regex to extract the top-level "message" field value from partial JSON.
        # Only matches the first occurrence before "files" to avoid matching
        # "message" keys inside file content strings.
        message_re = re.compile(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"files"')

        max_retries = 3
        for attempt in range(max_retries + 1):
            client = httpx.AsyncClient(timeout=httpx.Timeout(self._timeout, connect=self._connect_timeout))
            try:
                async with client.stream(
                    "POST", self._target_url, json=payload, headers=headers
                ) as response:
                    if response.status_code == 401:
                        raise RuntimeError("AI provider authentication failed (401). Check your JWT_TOKEN.")
                    if response.status_code == 404:
                        raise RuntimeError(f"AI provider endpoint not found (404). Check your TARGET_URL.")
                    if response.status_code == 429:
                        wait = _parse_retry_after(response)
                        if attempt >= max_retries:
                            raise RateLimitError(
                                retry_after=wait,
                                message=f"AI provider rate limited (429). Retry after {wait}s. Max retries ({max_retries}) exceeded.",
                            )
                        logger.warning("AI provider rate limited (429). Retrying in %ds (attempt %d/%d)", wait, attempt + 1, max_retries)
                        await asyncio.sleep(wait)
                        # Exit stream context to retry outer loop
                        break
                    if not response.is_success:
                        raise RuntimeError(
                            f"AI provider returned {response.status_code}"
                        )

                    # Check if the response is SSE or regular JSON
                    content_type = response.headers.get("content-type", "")
                    is_sse = "text/event-stream" in content_type

                    if not is_sse:
                        # Regular JSON response (e.g. deepseek-v4-flash) — parse
                        # the full response and yield as a single event
                        body = await response.aread()
                        try:
                            data = json.loads(body)
                            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                            content = body.decode("utf-8", errors="replace")

                        if content:
                            accumulated_content = content
                            # Stream the full message
                            yield {"type": "message_chunk", "delta": content}
                        break  # Exit the streaming loop — we have the full response

                    # Read SSE stream
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue

                        data_str = line[6:].strip()

                        # Skip [DONE] sentinel
                        if data_str == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # Extract delta content from OpenAI streaming format
                        try:
                            delta = chunk["choices"][0]["delta"]
                        except (KeyError, IndexError, TypeError):
                            continue

                        content_delta = delta.get("content", "")
                        if not content_delta:
                            continue

                        accumulated_content += content_delta

                        # --- Extract and stream message text in real-time ---
                        # The AI generates: {"message": "Hello...", "files": [...]}
                        # We extract just the message text value and send it as
                        # clean message_chunk deltas. The frontend never sees raw JSON.
                        #
                        # Strategy: try to parse the "message" field value from the
                        # accumulated JSON using a regex that matches the message
                        # value before the "files" key appears.
                        msg_match = message_re.search(accumulated_content)
                        if msg_match:
                            current_message = msg_match.group(1)
                            new_part = current_message[len(prev_message):]
                            if new_part:
                                prev_message = current_message
                                yield {"type": "message_chunk", "delta": new_part}
                        else:
                            # Before the regex can match, the message value is still
                            # being built. Try a simpler extraction: find text between
                            # '"message": "' and the next '", "'
                            # This handles the early tokens before "files" appears.
                            simple_match = re.search(r'"message"\s*:\s*"((?:[^"\\]|\\.)*)', accumulated_content)
                            if simple_match:
                                current_message = simple_match.group(1)
                                new_part = current_message[len(prev_message):]
                                if new_part:
                                    prev_message = current_message
                                    yield {"type": "message_chunk", "delta": new_part}

                        # --- Try to parse partial JSON for file content ---
                        partial = re.sub(r"^```(?:json)?\s*", "", accumulated_content.strip())
                        partial = re.sub(r"\s*```$", "", partial)
                        first_brace = partial.find("{")
                        last_brace = partial.rfind("}")
                        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                            partial = partial[first_brace : last_brace + 1]

                        try:
                            parsed = json.loads(partial)
                            raw_files = parsed.get("files", [])
                            for f in raw_files:
                                fpath = f.get("path", "")
                                fcontent = f.get("content", "")
                                ftype = f.get("file_type", "other")
                                if not fpath:
                                    continue

                                # Announce new files
                                if fpath not in announced_files:
                                    announced_files.add(fpath)
                                    yield {
                                        "type": "file_start",
                                        "path": fpath,
                                        "file_type": ftype,
                                    }

                                # Stream new content
                                prev_content = streamed_file_content.get(fpath, "")
                                if fcontent.startswith(prev_content) and len(fcontent) > len(prev_content):
                                    new_content = fcontent[len(prev_content):]
                                    streamed_file_content[fpath] = fcontent
                                    yield {
                                        "type": "file_chunk",
                                        "path": fpath,
                                        "delta": new_content,
                                    }
                                elif not fcontent.startswith(prev_content) and len(fcontent) > len(prev_content):
                                    streamed_file_content[fpath] = fcontent
                                    yield {
                                        "type": "file_chunk",
                                        "path": fpath,
                                        "delta": fcontent,
                                    }
                        except (json.JSONDecodeError, RuntimeError):
                            pass

            except Exception:
                raise
            finally:
                await client.aclose()

        # After the stream ends, parse the full accumulated content
        try:
            message, files = _parse_final_json(accumulated_content, existing_files)
        except (json.JSONDecodeError, RuntimeError) as e:
            # On parse failure, preserve existing files so the project isn't wiped
            fallback_files = existing_files or []
            yield {
                "type": "done",
                "message": prev_message or accumulated_content,
                "files": [f.model_dump() for f in fallback_files],
            }
            return

        # Yield file_done for any files that were streamed
        for f in files:
            if f.path not in announced_files:
                yield {
                    "type": "file_start",
                    "path": f.path,
                    "file_type": f.file_type.value,
                }
                yield {"type": "file_chunk", "path": f.path, "delta": f.content}
            else:
                # Check if final content differs from streamed content and send corrective delta
                streamed = streamed_file_content.get(f.path, "")
                if streamed != f.content:
                    yield {
                        "type": "file_chunk",
                        "path": f.path,
                        "delta": f.content,
                    }
            yield {"type": "file_done", "path": f.path}

        yield {
            "type": "done",
            "message": message,
            "files": [f.model_dump() for f in files],
        }

    async def analyze_design(
        self,
        image_data_uri: str,
        filename: str = "design",
        mime_type: str = "image/png",
    ) -> str:
        """Stage 1: Analyze a design image — delegates to HttpAIProvider."""
        provider = HttpAIProvider(
            self._target_url, self._jwt_token, self._model, self._timeout
        )
        return await provider.analyze_design(image_data_uri, filename, mime_type)

    async def generate_from_spec(
        self,
        design_description: str,
        user_prompt: str = "",
    ) -> tuple[str, list[ProjectFile]]:
        """Stage 2: Generate code from description — delegates to HttpAIProvider."""
        provider = HttpAIProvider(
            self._target_url, self._jwt_token, self._model, self._timeout
        )
        return await provider.generate_from_spec(design_description, user_prompt)


def create_provider() -> BaseAIProvider:
    """Factory — create an AI provider from the current settings."""
    return StreamingHttpAIProvider(
        target_url=settings.target_url,
        jwt_token=settings.jwt_token,
        model=settings.model,
        timeout=float(settings.timeout_seconds),
    )


def create_design_upload_provider() -> BaseAIProvider:
    """Factory — create an AI provider for design upload (vision) tasks.

    Uses ``design_upload_target_url`` / ``design_upload_jwt_token`` /
    ``design_upload_model`` if set, otherwise falls back to the main AI config.
    This allows pointing design uploads at a different provider (e.g. a vision model).
    """
    target_url = settings.design_upload_target_url or settings.target_url
    jwt_token = settings.design_upload_jwt_token or settings.jwt_token
    model = settings.design_upload_model or settings.model

    if not settings.design_upload_target_url:
        logger.info("  [Upload] DESIGN_UPLOAD_TARGET_URL not set — falling back to TARGET_URL")
    if not settings.design_upload_jwt_token:
        logger.info("  [Upload] DESIGN_UPLOAD_JWT_TOKEN not set — falling back to JWT_TOKEN")
    if not settings.design_upload_model:
        logger.info("  [Upload] DESIGN_UPLOAD_MODEL not set — falling back to MODEL")

    logger.info("  [Upload] Design upload provider — URL: %s, model: %s", target_url, model)
    return HttpAIProvider(
        target_url=target_url,
        jwt_token=jwt_token,
        model=model,
        timeout=float(settings.timeout_seconds),
    )
