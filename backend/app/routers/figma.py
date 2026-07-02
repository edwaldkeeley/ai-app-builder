"""REST endpoints for Figma design import via URL.

Only the URL import endpoint is kept. OAuth-based import has been removed.
Users provide a Figma URL and an optional personal access token.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, HTTPException, status

from app.models.schemas import (
    FigmaUrlImportRequest,
    GenerateResponse,
    ProjectCreate,
)
from app.services.ai_service import BaseAIProvider, RateLimitError, _FIGMA_SYSTEM_PROMPT
from app.services.figma_service import FigmaApiError, FigmaRateLimitError, FigmaService
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/figma", tags=["figma"])

_figma: FigmaService | None = None
_provider: BaseAIProvider | None = None
_service: ProjectService | None = None


def set_dependencies(
    figma: FigmaService,
    provider: BaseAIProvider | None = None,
    service: ProjectService | None = None,
) -> None:
    global _figma, _provider, _service
    _figma = figma
    _provider = provider
    _service = service


# ── URL import endpoint (no OAuth required) ───────────────────


@router.post("/import-url", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def import_figma_url(body: FigmaUrlImportRequest):
    """Import a Figma design by URL and generate code from it.

    Accepts a Figma file URL (or bare file key) and an optional personal
    access token. If a token is provided, it is used to fetch the file
    directly from the Figma REST API.

    This endpoint works for public Figma files without any authentication,
    and for private files when a personal access token is provided.
    """
    if _figma is None or _provider is None or _service is None:
        raise HTTPException(
            status_code=503,
            detail="Required services not initialized",
        )

    # Extract the file key from the URL
    try:
        file_key = FigmaService.extract_file_key(body.figma_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch the Figma file data
    if not body.access_token:
        raise HTTPException(
            status_code=401,
            detail="A Figma personal access token is required. "
            "Generate one at https://www.figma.com/settings",
        )

    try:
        response = await _figma.request_with_retry(
            "GET",
            f"https://api.figma.com/v1/files/{file_key}",
            headers={"X-Figma-Token": body.access_token},
            timeout=60,
        )
        file_data = response.json()
    except FigmaRateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={"message": str(e), "retry_after": e.retry_after},
        )
    except FigmaApiError as e:
        logger.exception("Figma API request failed")
        raise HTTPException(
            status_code=502,
            detail=f"Figma API returned {e.status}: {e}",
        )
    except httpx.RequestError as e:
        logger.exception("Figma API request failed")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach Figma API: {e}",
        )

    # Build a structured design prompt from the Figma data
    design_prompt = _figma.build_design_prompt(file_data)
    design_name = file_data.get("name", "Figma Import")

    # Create a new project
    project = await _service.create(
        ProjectCreate(
            name=design_name,
            description=f"Imported from Figma URL: {body.figma_url}",
        )
    )
    project_id = project.id

    # Generate code from the design prompt
    try:
        message, files = await _provider.generate(
            design_prompt,
            system_prompt_override=_FIGMA_SYSTEM_PROMPT,
        )
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={"message": str(e), "retry_after": e.retry_after},
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Persist files and chat messages
    await _service.upsert_files_transactional(project_id, files)
    # Truncate the design prompt for chat history to avoid hitting the 100k char limit
    user_message = design_prompt[:50000] + "\n\n[design prompt truncated]" if len(design_prompt) > 50000 else design_prompt
    await _service.save_chat_message(project_id, "user", user_message)
    await _service.save_chat_message(project_id, "assistant", message, files)

    return GenerateResponse(
        project_id=project_id,
        project_name=design_name,
        message=message,
        files=files,
    )
