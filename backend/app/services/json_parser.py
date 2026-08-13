"""JSON and markdown parsing utilities for AI provider responses.

Handles the messy reality of LLM output: partial JSON, markdown code blocks,
single quotes, trailing commas, and other common LLM output quirks.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.models.schemas import FileType, ProjectFile

logger = logging.getLogger(__name__)


def extract_code_blocks(content: str) -> list[tuple[str, str]]:
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

    Maps language tags to filenames: html -> index.html, css -> style.css,
    js/javascript -> script.js. Any text before the first code block is
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
        "typescript": "script.ts",
        "ts": "script.ts",
        "tsx": "component.tsx",
        "jsx": "component.jsx",
        "json": "data.json",
        "python": "script.py",
        "py": "script.py",
        "markdown": "README.md",
        "md": "README.md",
        "svg": "icon.svg",
    }
    lang_to_type = {
        "html": FileType.html,
        "css": FileType.css,
        "js": FileType.js,
        "javascript": FileType.js,
        "typescript": FileType.ts,
        "ts": FileType.ts,
        "tsx": FileType.tsx,
        "jsx": FileType.jsx,
        "json": FileType.json,
        "python": FileType.python,
        "py": FileType.python,
        "markdown": FileType.markdown,
        "md": FileType.markdown,
        "svg": FileType.svg,
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


def _replace_single_quote_json(s: str) -> str:
    """Replace single quotes used as JSON string delimiters, NOT apostrophes.

    Strategy: walk through the string character by character. Track whether
    we're inside a double-quoted string. A single quote is a JSON delimiter
    only when we are NOT inside a double-quoted string. Apostrophes inside
    double-quoted values are left untouched.

    This is imperfect — it can't distinguish a JSON value quoted with single
    quotes from a ``don't`` in unquoted text — but it's far better than the
    blanket replacement.
    """
    result = []
    in_double = False
    escaped = False
    for ch in s:
        if escaped:
            result.append(ch)
            escaped = False
            continue
        if ch == '\\':
            result.append(ch)
            escaped = True
            continue
        if ch == '"':
            in_double = not in_double
            result.append(ch)
            continue
        if ch == "'" and not in_double:
            result.append('"')
            continue
        result.append(ch)
    return ''.join(result)


def _repair_json(content: str) -> str:
    """Attempt to repair common JSON issues from LLM output.

    Handles:
    - Single quotes instead of double quotes (preserves apostrophes)
    - Trailing commas before ``]`` or ``}``
    - Missing commas between key-value pairs or array elements
    - Unquoted string values (e.g. ``true``, ``null`` — these are valid JSON)
    """
    # Replace single quotes used as JSON delimiters, NOT apostrophes inside words
    content = _replace_single_quote_json(content)

    # Strip trailing commas before ] or }
    content = re.sub(r",\s*([}\]])", r"\1", content)

    # Insert missing commas: a closing quote followed by whitespace then an opening
    # quote, but NOT separated by a colon (which would be a key:value pair).
    # Pattern: "value" "key" -> "value", "key"  (missing comma between array elements
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


def parse_final_json(
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
        blocks = extract_code_blocks(content)
        if blocks:
            return _code_blocks_to_files(content, blocks, existing_files)
        # No code blocks found — treat entire response as conversational message
        logger.warning("No code blocks found in AI response, treating as conversational message only")
        return content.strip(), existing_files or []

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

        ai_files_map[f.get("path", "")] = ProjectFile(
            path=f.get("path", ""),
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
