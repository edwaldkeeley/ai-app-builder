"""Tests for AI service: JSON parsing, file validation, payload building,
retry-after parsing, and the Figma system prompt.

These tests do NOT call the real AI provider — they test the utility
functions that process AI responses.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.models.schemas import FileType, ProjectFile
from app.services.ai_service import (
    _FIGMA_SYSTEM_PROMPT,
    _SYSTEM_PROMPT,
    _build_payload,
    _parse_final_json,
    _validate_generated_files,
)
from app.services.utils import parse_retry_after as _parse_retry_after


# ── _parse_final_json tests ───────────────────────────────────


class TestParseFinalJson:
    def test_parse_simple_response(self):
        content = json.dumps({
            "message": "Created a page.",
            "files": [
                {"path": "index.html", "content": "<html></html>", "file_type": "html"},
                {"path": "style.css", "content": "body {}", "file_type": "css"},
            ],
        })
        message, files = _parse_final_json(content)
        assert message == "Created a page."
        assert len(files) == 2
        assert files[0].path == "index.html"
        assert files[0].file_type == FileType.html

    def test_parse_with_markdown_code_block(self):
        content = "```json\n{\"message\": \"Hi\", \"files\": []}\n```"
        message, files = _parse_final_json(content)
        assert message == "Hi"
        assert files == []

    def test_parse_with_extra_text(self):
        content = "Here's the code:\n{\"message\": \"Done\", \"files\": []}\nLet me know if you need changes."
        message, files = _parse_final_json(content)
        assert message == "Done"

    def test_parse_merges_with_existing_files(self):
        existing = [
            ProjectFile(path="keep.html", content="<!-- keep -->", file_type=FileType.html),
        ]
        content = json.dumps({
            "message": "Updated",
            "files": [
                {"path": "new.html", "content": "<!-- new -->", "file_type": "html"},
            ],
        })
        message, files = _parse_final_json(content, existing)
        paths = {f.path for f in files}
        assert "keep.html" in paths  # existing file preserved
        assert "new.html" in paths  # new file added

    def test_parse_ai_overrides_existing(self):
        existing = [
            ProjectFile(path="index.html", content="<!-- old -->", file_type=FileType.html),
        ]
        content = json.dumps({
            "message": "Updated",
            "files": [
                {"path": "index.html", "content": "<!-- new -->", "file_type": "html"},
            ],
        })
        message, files = _parse_final_json(content, existing)
        index = next(f for f in files if f.path == "index.html")
        assert index.content == "<!-- new -->"  # AI content wins

    def test_parse_unknown_file_type_defaults_to_other(self):
        content = json.dumps({
            "message": "",
            "files": [
                {"path": "data.txt", "content": "data", "file_type": "text"},
            ],
        })
        message, files = _parse_final_json(content)
        assert files[0].file_type == FileType.other

    def test_parse_empty_files_array(self):
        content = json.dumps({"message": "No files", "files": []})
        message, files = _parse_final_json(content)
        assert message == "No files"
        assert files == []

    def test_parse_no_files_key(self):
        content = json.dumps({"message": "No files key"})
        message, files = _parse_final_json(content)
        assert message == "No files key"
        assert files == []


# ── _validate_generated_files tests ───────────────────────────


class TestValidateGeneratedFiles:
    def test_all_files_present(self):
        files = [
            ProjectFile(path="index.html", content="<html><head><link rel=\"stylesheet\" href=\"style.css\"></head><body><title>Test</title></body></html><script src=\"script.js\"></script>", file_type=FileType.html),
            ProjectFile(path="style.css", content="body { color: red; margin: 0; padding: 0; font-family: sans-serif; }", file_type=FileType.css),
            ProjectFile(path="script.js", content="// js", file_type=FileType.js),
        ]
        warnings = _validate_generated_files(files)
        assert len(warnings) == 0

    def test_missing_index_html(self):
        files = [
            ProjectFile(path="style.css", content="body {}", file_type=FileType.css),
        ]
        warnings = _validate_generated_files(files)
        assert any("Missing required file: index.html" in w for w in warnings)

    def test_missing_style_css(self):
        files = [
            ProjectFile(path="index.html", content="<html></html>", file_type=FileType.html),
        ]
        warnings = _validate_generated_files(files)
        assert any("Missing required file: style.css" in w for w in warnings)

    def test_missing_script_js(self):
        files = [
            ProjectFile(path="index.html", content="<html></html>", file_type=FileType.html),
            ProjectFile(path="style.css", content="body {}", file_type=FileType.css),
        ]
        warnings = _validate_generated_files(files)
        assert any("Missing required file: script.js" in w for w in warnings)

    def test_html_missing_body_tag(self):
        files = [
            ProjectFile(path="index.html", content="<html><head></head></html>", file_type=FileType.html),
            ProjectFile(path="style.css", content="body {}", file_type=FileType.css),
            ProjectFile(path="script.js", content="// js", file_type=FileType.js),
        ]
        warnings = _validate_generated_files(files)
        assert any("missing <body> tag" in w for w in warnings)

    def test_html_missing_title_tag(self):
        files = [
            ProjectFile(path="index.html", content="<html><body></body></html>", file_type=FileType.html),
            ProjectFile(path="style.css", content="body {}", file_type=FileType.css),
            ProjectFile(path="script.js", content="// js", file_type=FileType.js),
        ]
        warnings = _validate_generated_files(files)
        assert any("missing <title> tag" in w for w in warnings)

    def test_html_missing_css_link(self):
        files = [
            ProjectFile(path="index.html", content="<html><body></body></html>", file_type=FileType.html),
            ProjectFile(path="style.css", content="body {}", file_type=FileType.css),
            ProjectFile(path="script.js", content="// js", file_type=FileType.js),
        ]
        warnings = _validate_generated_files(files)
        assert any("does not link to style.css" in w for w in warnings)

    def test_empty_css_warning(self):
        files = [
            ProjectFile(path="index.html", content="<html><body></body></html>", file_type=FileType.html),
            ProjectFile(path="style.css", content="", file_type=FileType.css),
            ProjectFile(path="script.js", content="// js", file_type=FileType.js),
        ]
        warnings = _validate_generated_files(files)
        assert any("style.css is empty" in w for w in warnings)

    def test_short_css_warning(self):
        files = [
            ProjectFile(path="index.html", content="<html><body></body></html>", file_type=FileType.html),
            ProjectFile(path="style.css", content="a {}", file_type=FileType.css),
            ProjectFile(path="script.js", content="// js", file_type=FileType.js),
        ]
        warnings = _validate_generated_files(files)
        assert any("style.css seems too short" in w for w in warnings)


# ── _build_payload tests ──────────────────────────────────────


class TestBuildPayload:
    def test_basic_payload_structure(self):
        payload = _build_payload("Hello")
        assert "messages" in payload
        assert len(payload["messages"]) >= 1
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][-1]["role"] == "user"
        assert payload["messages"][-1]["content"] == "Hello"

    def test_payload_with_existing_files(self):
        files = [
            ProjectFile(path="index.html", content="<html></html>", file_type=FileType.html),
        ]
        payload = _build_payload("Update", existing_files=files)
        # Should have system prompt + file context + user message
        assert len(payload["messages"]) == 3
        assert "Current project files" in payload["messages"][1]["content"]

    def test_payload_with_chat_history(self):
        history = [
            {"role": "user", "content": "First message"},
            {"role": "assistant", "content": "First response"},
        ]
        payload = _build_payload("Second message", chat_history=history)
        # system + 2 history + user = 4
        assert len(payload["messages"]) == 4

    def test_payload_chat_history_truncated(self):
        history = [{"role": "user", "content": "x" * 5000}]  # exceeds 2000 char limit
        payload = _build_payload("Hi", chat_history=history)
        # The content should be truncated
        msg = payload["messages"][1]
        assert len(msg["content"]) < 3000
        assert "[content truncated]" in msg["content"]

    def test_payload_with_system_prompt_override(self):
        override = "You are a test bot."
        payload = _build_payload("Hi", system_prompt_override=override)
        assert payload["messages"][0]["content"] == override

    def test_payload_default_system_prompt(self):
        payload = _build_payload("Hi")
        assert payload["messages"][0]["content"] == _SYSTEM_PROMPT

    def test_payload_no_max_tokens_by_default(self):
        payload = _build_payload("Hi")
        assert "max_tokens" not in payload

    def test_payload_with_max_tokens(self):
        payload = _build_payload("Hi", max_tokens=1000)
        assert payload.get("max_tokens") == 1000

    def test_payload_zero_max_tokens_omitted(self):
        payload = _build_payload("Hi", max_tokens=0)
        assert "max_tokens" not in payload


# ── _parse_retry_after tests ──────────────────────────────────


class TestParseRetryAfter:
    def test_integer_header(self):
        response = httpx.Response(429, headers={"Retry-After": "30"})
        assert _parse_retry_after(response) == 30

    def test_integer_header_capped_at_120(self):
        response = httpx.Response(429, headers={"Retry-After": "999"})
        assert _parse_retry_after(response) == 120

    def test_no_header_falls_back_to_default(self):
        response = httpx.Response(429)
        assert _parse_retry_after(response) == 10

    def test_no_header_custom_default(self):
        response = httpx.Response(429)
        assert _parse_retry_after(response, default=5) == 5

    def test_success_response_not_affected(self):
        response = httpx.Response(200)
        assert _parse_retry_after(response) == 10


# ── System prompt tests ───────────────────────────────────────


class TestSystemPrompts:
    def test_figma_prompt_contains_role(self):
        assert "pixel-perfect" in _FIGMA_SYSTEM_PROMPT

    def test_figma_prompt_has_rules(self):
        assert "Rules" in _FIGMA_SYSTEM_PROMPT

    def test_figma_prompt_has_output_format(self):
        assert "Output format" in _FIGMA_SYSTEM_PROMPT
        assert "files" in _FIGMA_SYSTEM_PROMPT

    def test_figma_prompt_has_three_files(self):
        assert "index.html" in _FIGMA_SYSTEM_PROMPT
        assert "style.css" in _FIGMA_SYSTEM_PROMPT
        assert "script.js" in _FIGMA_SYSTEM_PROMPT

    def test_default_prompt_has_guidelines(self):
        assert "GUIDELINES" in _SYSTEM_PROMPT
        assert "OUTPUT FORMAT" in _SYSTEM_PROMPT
