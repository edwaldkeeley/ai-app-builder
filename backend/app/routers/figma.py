"""REST endpoints for Figma design import via URL.

Only the URL import endpoint is kept. OAuth-based import has been removed.
Users provide a Figma URL and an optional personal access token.
"""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.models.schemas import (
    FigmaDebugPromptResponse,
    FigmaUrlImportRequest,
    GenerateResponse,
    ProjectCreate,
)
from app.routers.dependencies import get_current_user
from app.services.ai_service import BaseAIProvider, RateLimitError
from app.services.figma_filter import (
    classify_canvas,
    extract_file_key,
    get_canvas_dimensions,
    get_canvases,
)
from app.services.figma_service import FigmaService
from app.services.figma_tree_walker import build_design_prompt, count_nodes
from app.services.figma_types import FigmaApiError, FigmaRateLimitError
from app.services.project_service import ProjectService
from app.services.prompts import _FIGMA_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


def length_safe(text: str, start: int | None, end: int | None) -> int:
    """Safely compute substring length, returning 0 if start is -1."""
    if start is None or start < 0:
        return 0
    if end is None or end < 0:
        return max(0, len(text) - start)
    return max(0, end - start)

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


# ── URL import endpoint ────────────────────────────────────────


@router.post("/import-url", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def import_figma_url(body: FigmaUrlImportRequest, current_user: dict = Depends(get_current_user)):
    """Import a Figma design by URL and generate code from it.

    Accepts a Figma file URL (or bare file key) and a personal access token.
    The Figma file is fetched via the REST API and converted to code.

    Results are cached for 5 minutes. Set ``force_refresh=true`` to bypass
    the cache and fetch fresh data from Figma.
    """
    if _figma is None or _provider is None or _service is None:
        raise HTTPException(
            status_code=503,
            detail="Required services not initialized",
        )

    # Extract the file key from the URL
    try:
        file_key = extract_file_key(body.figma_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Clear cache if force_refresh is requested
    if body.force_refresh:
        await FigmaService.clear_cache(file_key)
        logger.info("Cache bypassed for file key: %s", file_key)

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
            detail={"message": f"Figma API returned {e.status}: {e}"},
        )
    except httpx.RequestError as e:
        logger.exception("Figma API request failed")
        raise HTTPException(
            status_code=502,
            detail={"message": f"Failed to reach Figma API: {e}"},
        )

    # Build a structured design prompt from the Figma data
    design_prompt = build_design_prompt(file_data)
    design_name = file_data.get("name", "Figma Import")

    # Log prompt composition
    prompt_chars = len(design_prompt)
    prompt_tokens_est = prompt_chars // 3
    # Break down the prompt sections (rough heuristic based on known markers)
    tree_start = design_prompt.find("## Design Tree Summary")
    json_start = design_prompt.find("## Filtered Figma JSON")
    instr_start = design_prompt.find("## Instructions")
    tree_size = length_safe(design_prompt, tree_start, json_start)
    json_size = length_safe(design_prompt, json_start, instr_start)
    instr_size = length_safe(design_prompt, instr_start, None)
    logger.info(
        "Figma prompt composition: %d total chars (~%d tokens) | "
        "tree=%d json=%d instructions=%d | name=%s",
        prompt_chars, prompt_tokens_est,
        tree_size, json_size, instr_size,
        design_name,
    )

    # Create a new project
    project = await _service.create(
        ProjectCreate(
            name=design_name,
            description=f"Imported from Figma URL: {body.figma_url}",
        ),
        user_id=current_user["id"],
    )
    project_id = project.id

    # Generate code from the design prompt
    try:
        message, files = await _provider.generate(
            design_prompt,
            system_prompt_override=_FIGMA_SYSTEM_PROMPT,
        )
        # Log AI response diagnostics
        response_chars = len(message) + sum(len(f.content or "") for f in files)
        logger.info(
            "Figma AI response: %s files, %d total chars, message=%d chars | names=%s",
            len(files), response_chars, len(message),
            [f.path for f in files],
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


# ── Debug endpoint (no AI call) ──────────────────────────────


@router.post("/debug-prompt", status_code=status.HTTP_200_OK)
async def debug_figma_prompt(body: FigmaUrlImportRequest, current_user: dict = Depends(get_current_user)):
    """Fetch a Figma file and return the prompt that would be sent to the AI, without calling the AI.

    This is a diagnostic tool. Use it to inspect the prompt quality before doing a real import.
    The prompt is constructed from the Design Tree Summary + Filtered Figma JSON + Instructions.
    """
    if _figma is None:
        raise HTTPException(status_code=503, detail="Figma service not initialized")

    # Extract the file key
    try:
        file_key = extract_file_key(body.figma_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch the Figma file data (respects cache)
    if not body.access_token:
        raise HTTPException(
            status_code=401,
            detail="A Figma personal access token is required.",
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
        raise HTTPException(status_code=429, detail={"message": str(e), "retry_after": e.retry_after})
    except FigmaApiError as e:
        logger.exception("Figma API request failed")
        raise HTTPException(status_code=502, detail={"message": f"Figma API returned {e.status}: {e}"})
    except httpx.RequestError as e:
        logger.exception("Figma API request failed")
        raise HTTPException(status_code=502, detail={"message": f"Failed to reach Figma API: {e}"})

    # Build the prompt
    design_prompt = build_design_prompt(file_data)
    figma_name = file_data.get("name", "Untitled")

    # Compute metadata
    prompt_chars = len(design_prompt)
    estimated_tokens = prompt_chars // 3

    tree_summary_pos = design_prompt.find("## Design Tree Summary")
    json_pos = design_prompt.find("## Filtered Figma JSON")

    # Tree capped?
    tree_capped = "tree truncated" in design_prompt

    # Node count — use proper tree walk, not text heuristic
    document = file_data.get("document")
    canvas_list = get_canvases(document) if document and isinstance(document, dict) else []
    tree_node_count = sum(count_nodes(c) for c in canvas_list)

    # Per-canvas info
    canvas_info = []
    for i, canvas in enumerate(canvas_list):
        cname = canvas.get("name", f"Canvas {i}")
        label = classify_canvas(canvas)
        w, h = get_canvas_dimensions(canvas)
        node_count = count_nodes(canvas)
        canvas_info.append({
            "name": cname,
            "type": label,
            "width": w,
            "height": h,
            "node_count": node_count,
        })

    # Filtered JSON size
    json_capped = "JSON truncated" in design_prompt
    json_original_size = 0
    if json_pos >= 0:
        json_section = design_prompt[json_pos:]
        if json_capped:
            json_original_size = 40_001  # capped at 40k, marker adds 1
        else:
            json_block_start = json_section.find("```json")
            json_block_end = json_section.find("```", json_block_start + 7) if json_block_start >= 0 else -1
            if json_block_end > json_block_start:
                json_original_size = json_block_end - json_block_start - 7

    return FigmaDebugPromptResponse(
        figma_file_name=figma_name,
        figma_file_key=file_key,
        tree_node_count=tree_node_count,
        tree_capped=tree_capped,
        filtered_json_size=json_original_size,
        filtered_json_capped=json_capped,
        total_chars=prompt_chars,
        estimated_tokens=estimated_tokens,
        canvas_info=canvas_info,
        prompt_text=design_prompt,
    )


# ── Cache management ──────────────────────────────────────────


@router.get("/cache", status_code=status.HTTP_200_OK)
async def get_cache_info(current_user: dict = Depends(get_current_user)):
    """Get Figma file cache statistics."""
    if _figma is None:
        raise HTTPException(status_code=503, detail="Figma service not initialized")
    return FigmaService.get_cache_info()


@router.delete("/cache", status_code=status.HTTP_200_OK)
async def clear_cache(file_key: str | None = None, current_user: dict = Depends(get_current_user)):
    """Clear the Figma file cache.

    If ``file_key`` is provided, only that file's cache is cleared.
    Otherwise, the entire cache is cleared.
    """
    if _figma is None:
        raise HTTPException(status_code=503, detail="Figma service not initialized")
    cleared = await FigmaService.clear_cache(file_key)
    return {"cleared": cleared, "message": f"Cleared {cleared} cache entr{'y' if cleared == 1 else 'ies'}"}
