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
from typing import Any, AsyncIterator

import httpx

from app.config import settings
from app.models.schemas import ProjectFile
from app.services.file_validator import fix_react_imports, validate_generated_files
from app.services.json_parser import parse_final_json
from app.services.prompts import (
    _DESIGN_ANALYSIS_PROMPT,
    _DESIGN_UPLOAD_SYSTEM_PROMPT,
    _REACT_SYSTEM_PROMPT,
    _SYSTEM_PROMPT,
    build_design_code_prompt,
)
from app.services.utils import parse_retry_after

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
        framework: str = "vanilla",
    ) -> tuple[str, list[ProjectFile]]:
        """Send a prompt and return (message, list of project files).

        Args:
            prompt: The latest user prompt.
            existing_files: Current files in the project (for context).
            chat_history: Previous conversation messages.
            system_prompt_override: Optional system prompt to use instead of the default.
            framework: "vanilla" or "react" — selects the appropriate system prompt.
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
        framework: str = "vanilla",
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


def _build_payload(
    prompt: str,
    existing_files: list[ProjectFile] | None = None,
    chat_history: list[dict[str, str]] | None = None,
    system_prompt_override: str | None = None,
    max_tokens: int | None = None,
    framework: str = "vanilla",
) -> dict[str, Any]:
    """Build the OpenAI-compatible messages payload.

    Args:
        prompt: The latest user prompt.
        existing_files: Current files in the project (sent as context).
        chat_history: Previous messages in the conversation.
        system_prompt_override: Optional system prompt to use instead of the default.
        max_tokens: Maximum output tokens for the AI response.
        framework: "vanilla" or "react" — selects the appropriate system prompt.
    """
    if system_prompt_override:
        system_prompt = system_prompt_override
    elif framework == "react":
        system_prompt = _REACT_SYSTEM_PROMPT
    else:
        system_prompt = _SYSTEM_PROMPT
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
        framework: str = "vanilla",
    ) -> tuple[str, list[ProjectFile]]:
        headers = {
            "Authorization": f"Bearer {self._jwt_token}",
            "Content-Type": "application/json",
        }

        payload = _build_payload(prompt, existing_files, chat_history, system_prompt_override, max_tokens=settings.max_tokens, framework=framework)
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
                wait = parse_retry_after(response)
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

        message, files = parse_final_json(content, existing_files)

        # Fix React import patterns in .jsx files
        if framework == "react":
            files = fix_react_imports(files)

        # Validate generated files and log warnings
        warnings = validate_generated_files(files, framework=framework)
        if warnings:
            logger.warning("Generated file validation warnings (%d):", len(warnings))
            for w in warnings:
                logger.warning("  - %s", w)
            # Append warnings to the message so the frontend can display them
            if warnings:
                message += "\n\n**Note:** " + " ".join(warnings)

        # Self-correction: if critical files are missing, try one correction pass
        critical_warnings = [w for w in warnings if w.startswith("Missing required")]
        if critical_warnings and framework == "react":
            logger.info("Critical validation warnings — attempting self-correction")
            correction_prompt = (
                "The previous response had issues. Please fix the following:\n"
                + "\n".join(f"- {w}" for w in critical_warnings)
                + "\n\nMake sure App.jsx uses proper ES module imports:\n"
                + '  import React, { useState } from "react";\n'
                + "  import { createRoot } from 'react-dom/client';\n\n"
                + "Output the COMPLETE corrected files as JSON."
            )
            try:
                correction_payload = _build_payload(
                    correction_prompt,
                    existing_files=files,
                    chat_history=chat_history,
                    framework=framework,
                    max_tokens=settings.max_tokens,
                )
                correction_payload["model"] = self._model
                async with httpx.AsyncClient(timeout=httpx.Timeout(self._timeout, connect=self._connect_timeout)) as client:
                    correction_response = await client.post(self._target_url, json=correction_payload, headers=headers)
                if correction_response.is_success:
                    correction_data = correction_response.json()
                    correction_content = correction_data["choices"][0]["message"]["content"]
                    if correction_content and correction_content.strip():
                        correction_message, correction_files = parse_final_json(correction_content, files)
                        if framework == "react":
                            correction_files = fix_react_imports(correction_files)
                        # Only use correction if it actually fixed the missing files
                        correction_map = {f.path for f in correction_files}
                        original_map = {f.path for f in files}
                        if len(correction_map) > len(original_map):
                            logger.info("Self-correction added %d new files", len(correction_map - original_map))
                            message = correction_message
                            files = correction_files
            except Exception as e:
                logger.warning("Self-correction attempt failed: %s", e)

        return message, files

    async def generate_stream(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
        framework: str = "vanilla",
    ) -> AsyncIterator[dict[str, Any]]:
        """Non-streaming fallback — yields the complete result as a single event."""
        message, files = await self.generate(prompt, existing_files, chat_history, system_prompt_override, framework=framework)
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
                        wait = parse_retry_after(response)
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
        code_prompt = build_design_code_prompt(design_description, user_prompt)
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
        framework: str = "vanilla",
    ) -> tuple[str, list[ProjectFile]]:
        """Non-streaming fallback — delegates to HttpAIProvider logic."""
        provider = HttpAIProvider(
            self._target_url, self._jwt_token, self._model, self._timeout
        )
        return await provider.generate(prompt, existing_files, chat_history, system_prompt_override, framework=framework)

    async def generate_stream(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
        framework: str = "vanilla",
    ) -> AsyncIterator[dict[str, Any]]:
        headers = {
            "Authorization": f"Bearer {self._jwt_token}",
            "Content-Type": "application/json",
        }

        payload = _build_payload(prompt, existing_files, chat_history, system_prompt_override, max_tokens=settings.max_tokens, framework=framework)
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
        # Track whether we used the REST-to-SSE bridge (avoids double-emitting)
        _bridged = False
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
                        wait = parse_retry_after(response)
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
                        # Regular JSON response (e.g. deepseek-v4-flash) —
                        # bridge it into a simulated SSE stream by chunking
                        # the response text word-by-word for a progressive UX.
                        body = await response.aread()
                        try:
                            data = json.loads(body)
                            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                            content = body.decode("utf-8", errors="replace")

                        if content:
                            accumulated_content = content

                            # Parse the full JSON to extract message and files
                            try:
                                bridge_message, bridge_files = parse_final_json(content, existing_files)
                            except (json.JSONDecodeError, RuntimeError):
                                bridge_message = content
                                bridge_files = existing_files or []

                            # Yield message text in word-by-word chunks to simulate streaming
                            words = bridge_message.split(" ")
                            buffer = ""
                            for i, word in enumerate(words):
                                if buffer:
                                    buffer += " " + word
                                else:
                                    buffer = word
                                # Yield every 3-5 words for a natural streaming feel
                                if (i + 1) % 4 == 0 or i == len(words) - 1:
                                    yield {"type": "message_chunk", "delta": buffer}
                                    buffer = ""
                                    await asyncio.sleep(0.015)

                            # Yield any remaining buffered words
                            if buffer:
                                yield {"type": "message_chunk", "delta": buffer}

                            # Yield file events
                            for f in bridge_files:
                                yield {
                                    "type": "file_start",
                                    "path": f.path,
                                    "file_type": f.file_type.value,
                                }
                                # Chunk file content too if it's large
                                file_content = f.content
                                if len(file_content) > 500:
                                    chunk_size = 200
                                    for i in range(0, len(file_content), chunk_size):
                                        yield {
                                            "type": "file_chunk",
                                            "path": f.path,
                                            "delta": file_content[i:i + chunk_size],
                                        }
                                        await asyncio.sleep(0.01)
                                else:
                                    yield {
                                        "type": "file_chunk",
                                        "path": f.path,
                                        "delta": file_content,
                                    }
                                yield {"type": "file_done", "path": f.path}

                            # Set prev_message so the post-stream parsing doesn't
                            # re-emit the message as a corrective delta
                            prev_message = bridge_message
                            _bridged = True

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

        # If we used the REST-to-SSE bridge, all events were already yielded
        if _bridged:
            return

        # After the stream ends, parse the full accumulated content
        try:
            message, files = parse_final_json(accumulated_content, existing_files)
            # Fix React import patterns in .jsx files
            if framework == "react":
                files = fix_react_imports(files)
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
