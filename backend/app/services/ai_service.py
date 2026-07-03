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
from app.models.schemas import FileType, ProjectFile

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

_FIGMA_SYSTEM_PROMPT = (
    "You are a pixel-perfect frontend developer. Your ONLY job is to convert the provided "
    "Figma design JSON into exact HTML/CSS/JS code. Layout fidelity is your top priority.\n\n"
    "CRITICAL RULES:\n"
    "1. EXACT POSITIONS: Every element must be placed at its specified position and size. "
    "Use the exact pixel dimensions from the JSON.\n"
    "2. EXACT COLORS: Use the exact colors from the JSON. No substitutions.\n"
    "3. EXACT TYPOGRAPHY: Use the exact font families, sizes, weights, line heights, and "
    "text alignments from the JSON.\n"
    "4. EXACT SPACING: Match padding, gaps, margins, and border radii exactly.\n"
    "5. EXACT BORDERS: Match border widths, colors, and styles exactly.\n"
    "6. HIERARCHY: Preserve the parent-child nesting from the JSON tree. "
    "FRAME nodes with layoutMode become flexbox containers.\n"
    "7. IMAGES: Use colored divs or inline SVG as placeholders. Do NOT use external image URLs.\n"
    "8. THREE FILES: Create index.html, style.css, and script.js. "
    "index.html links to style.css (<link>) and script.js (<script src>). "
    "Use semantic HTML5 and modern CSS.\n"
    "9. NO CREATIVE FREEDOM: Do NOT add, remove, or rearrange elements. Do NOT change "
    "colors, fonts, or spacing. Reproduce the design exactly as specified.\n\n"
    "HOW TO READ THE FIGMA JSON:\n"
    "- The JSON is a filtered Figma document tree — only meaningful nodes are included\n"
    "- Each node has: type, name, width, height, x, y\n"
    "- FRAME nodes may have: fill, borderRadius, border, layoutMode, justifyContent,\n"
    "  alignItems, gap, padding, children\n"
    "- TEXT nodes have: text (content), textStyle (fontFamily, fontSize, fontWeight,\n"
    "  lineHeight, textAlign, color)\n"
    "- layoutMode 'row' = flex-direction: row, 'column' = flex-direction: column\n"
    "- Children are nested inside their parent node\n"
    "- Translate EVERY node into an HTML element with matching CSS\n\n"
    "OUTPUT FORMAT:\n"
    "Return ONLY valid JSON. Do NOT wrap the JSON in markdown code blocks.\n"
    'The JSON must have a "message" field (string, briefly describe what was built) '
    'and a "files" array where each file has: '
    '"path" (string), "content" (string), "file_type" (one of: html, css, javascript, json, python, other).\n'
    "Always include all three files: index.html (file_type: html), style.css (file_type: css), "
    "and script.js (file_type: javascript)."
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
    else:
        # Default to a high value if not configured — some providers default to very low values
        payload["max_tokens"] = 32000

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


def _parse_final_json(
    content: str,
    existing_files: list[ProjectFile] | None = None,
) -> tuple[str, list[ProjectFile]]:
    """Parse the final JSON response into (message, files).

    Merges AI output with existing files: only files the AI explicitly returns
    are updated; all other existing files are preserved unchanged.
    """
    # Strip markdown code block if present
    content = re.sub(r"^```(?:json)?\s*", "", content.strip())
    content = re.sub(r"\s*```$", "", content)

    # Find the first '{' and last '}' to extract JSON robustly
    first_brace = content.find("{")
    last_brace = content.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        content = content[first_brace : last_brace + 1]

    parsed = json.loads(content)
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

        return _parse_final_json(content, existing_files)

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

                        # --- Extract message text via regex ---
                        msg_match = message_re.search(accumulated_content)
                        if msg_match:
                            current_message = msg_match.group(1)
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


def create_provider() -> BaseAIProvider:
    """Factory — create an AI provider from the current settings."""
    return StreamingHttpAIProvider(
        target_url=settings.target_url,
        jwt_token=settings.jwt_token,
        model=settings.model,
    )
