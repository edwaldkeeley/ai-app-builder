"""AI provider abstraction and HTTP implementation.

The ``BaseAIProvider`` abstract class defines the interface for code generation.
``HttpAIProvider`` sends prompts to a configurable ``TARGET_URL`` using JWT
bearer authentication in OpenAI-compatible chat format and parses the response
into project files.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import settings
from app.models.schemas import FileType, ProjectFile


class BaseAIProvider(ABC):
    """Abstract interface for AI code generation."""

    @abstractmethod
    async def generate(self, prompt: str) -> list[ProjectFile]:
        """Send a prompt and return generated project files."""
        ...


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
        timeout: float = 120.0,
    ) -> None:
        self._target_url = target_url
        self._jwt_token = jwt_token
        self._model = model
        self._timeout = timeout

    async def generate(self, prompt: str) -> list[ProjectFile]:
        headers = {
            "Authorization": f"Bearer {self._jwt_token}",
            "Content-Type": "application/json",
        }

        # Instruct the model to return JSON with a files array
        system_prompt = (
            "You are a web developer. Generate the requested project files. "
            "Return ONLY valid JSON with NO markdown formatting, NO code blocks. "
            'The JSON must have a "files" array where each file has: '
            '"path" (string), "content" (string), "file_type" (one of: html, css, javascript, json, python, other).'
        )

        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "model": self._model,
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(self._target_url, json=payload, headers=headers)

        if response.status_code == 401:
            raise RuntimeError("AI provider authentication failed (401). Check your JWT_TOKEN.")
        if response.status_code == 404:
            raise RuntimeError(f"AI provider endpoint not found (404). Check your TARGET_URL.")
        if response.status_code == 429:
            raise RuntimeError("AI provider rate limited (429). Try again later.")
        if not response.is_success:
            raise RuntimeError(
                f"AI provider returned {response.status_code}: {response.text[:500]}"
            )

        data: dict[str, Any] = response.json()

        # Extract content from OpenAI-compatible response
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise RuntimeError(
                f"Unexpected AI response format. Expected 'choices[0].message.content'. Got: {str(data)[:300]}"
            ) from e

        # Strip markdown code block if present
        content = re.sub(r"^```(?:json)?\s*", "", content.strip())
        content = re.sub(r"\s*```$", "", content)

        # Find the first '{' and last '}' to extract JSON robustly,
        # even if the model returns extra text before/after the JSON block.
        first_brace = content.find("{")
        last_brace = content.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            content = content[first_brace : last_brace + 1]

        # Parse the JSON
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"AI response is not valid JSON: {e}. Content: {content[:500]}"
            ) from e

        raw_files = parsed.get("files", [])

        if not raw_files:
            raise RuntimeError(
                "AI provider returned no files. Expected a 'files' array in the response."
            )

        return [
            ProjectFile(
                path=f["path"],
                content=f.get("content", ""),
                file_type=f.get("file_type", FileType.other),
            )
            for f in raw_files
        ]


def create_provider() -> BaseAIProvider:
    """Factory — create an AI provider from the current settings."""
    return HttpAIProvider(
        target_url=settings.target_url,
        jwt_token=settings.jwt_token,
        model=settings.model,
    )
