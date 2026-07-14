"""REST endpoint for design image upload and code generation.

Users upload a design image (PNG, JPG, etc.) and the AI generates code from it.
The image is base64-encoded and sent as a data URI in the prompt.

Uses a two-stage pipeline:
1. Vision model analyzes the image → structured DesignSpec
2. Main code generation model → full HTML/CSS/JS code
"""

from __future__ import annotations

import base64
import io
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from app.config import settings
from app.models.schemas import GenerateResponse
from app.routers.dependencies import get_current_user
from app.services.ai_service import BaseAIProvider, RateLimitError
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["upload"])

_provider: BaseAIProvider | None = None
_vision_provider: BaseAIProvider | None = None
_service: ProjectService | None = None

ALLOWED_CONTENT_TYPES = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
    "image/bmp",
}


def set_dependencies(provider: BaseAIProvider, service: ProjectService) -> None:
    global _provider, _service
    _provider = provider
    _service = service


def set_vision_provider(provider: BaseAIProvider) -> None:
    """Override the provider used for design upload (vision) tasks."""
    global _vision_provider
    _vision_provider = provider


def _resize_image(raw_bytes: bytes, content_type: str) -> bytes:
    """Resize and compress an image for the vision model's limited context.

    The vision model (qwen2.5-vl-7b) has only ~8k tokens total.
    We resize to max 400px and use JPEG quality 60 to balance detail
    with token budget (image tokens + prompt + output must fit in 8192).
    """
    if not HAS_PIL:
        return raw_bytes

    try:
        img = PILImage.open(io.BytesIO(raw_bytes))
        w, h = img.size
        max_dim = 300
        if w > max_dim or h > max_dim:
            ratio = max_dim / max(w, h)
            new_w, new_h = int(w * ratio), int(h * ratio)
            img = img.resize((new_w, new_h), PILImage.LANCZOS)
        else:
            new_w, new_h = w, h
        # Convert to RGB (JPEG doesn't support RGBA) and save
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=50, optimize=True)
        result = buf.getvalue()
        logger.info("Resized upload image: %dx%d -> %dx%d (%d bytes, JPEG q50)", w, h, new_w, new_h, len(result))
        return result
    except Exception as e:
        logger.warning("Failed to resize upload image, sending original: %s", e)
        return raw_bytes


@router.post("/{project_id}/upload-design", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def upload_design(
    project_id: UUID,
    file: UploadFile = File(...),
    prompt: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """Upload a design image and generate code from it.

    Two-stage pipeline:
    1. Vision model analyzes the image → structured DesignSpec
    2. Main code generation model → full HTML/CSS/JS code

    Accepts a multipart form with an image file and an optional text prompt.
    """
    if _provider is None or _service is None:
        raise HTTPException(
            status_code=503,
            detail="Required services not initialized",
        )

    # Validate file type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. "
                   f"Allowed types: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    # Read file content
    raw_bytes = await file.read()

    # Validate file size
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb} MB.",
        )

    # Resize image for the vision model's tiny context window
    raw_bytes = _resize_image(raw_bytes, file.content_type or "image/png")

    # Validate project exists and user has access
    project = await _service.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id is not None and project.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Build the data URI
    b64_data = base64.b64encode(raw_bytes).decode("ascii")
    mime_type = file.content_type or "image/png"
    data_uri = f"data:{mime_type};base64,{b64_data}"

    # ── Stage 1: Vision model analyzes the image ────────────────
    vision = _vision_provider or _provider
    logger.info(
        "Stage 1: Analyzing design image with model=%s",
        getattr(vision, '_model', 'unknown'),
    )

    try:
        design_description = await vision.analyze_design(
            image_data_uri=data_uri,
            filename=file.filename or "design",
            mime_type=mime_type,
        )
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={"message": str(e), "retry_after": e.retry_after},
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    logger.info(
        "Stage 1 complete: %d chars of design description",
        len(design_description),
    )

    # ── Stage 2: Main model generates code from the description ──
    logger.info(
        "Stage 2: Generating code from design description with model=%s",
        getattr(_provider, '_model', 'unknown'),
    )

    try:
        message, files = await _provider.generate_from_spec(
            design_description=design_description,
            user_prompt=prompt,
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
    user_message = (
        f"Design upload: {file.filename or 'design'} ({mime_type}, {len(raw_bytes)} bytes)"
    )
    if prompt:
        user_message += f"\nPrompt: {prompt}"
    await _service.save_chat_message(project_id, "user", user_message)
    await _service.save_chat_message(project_id, "assistant", message, files)

    return GenerateResponse(
        project_id=project_id,
        project_name=project.name,
        message=message,
        files=files,
    )
