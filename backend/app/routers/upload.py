"""REST endpoint for design image upload and code generation.

Users upload a design image (PNG, JPG, etc.) and the AI generates code from it.
The image is base64-encoded and sent as a data URI in the prompt.
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
from app.services.ai_service import BaseAIProvider, RateLimitError, _DESIGN_UPLOAD_SYSTEM_PROMPT
from app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["upload"])

_provider: BaseAIProvider | None = None
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
    global _provider
    _provider = provider


@router.post("/{project_id}/upload-design", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def upload_design(
    project_id: UUID,
    file: UploadFile = File(...),
    prompt: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """Upload a design image and generate code from it.

    Accepts a multipart form with an image file and an optional text prompt.
    The image is base64-encoded and sent to the AI provider as a data URI.
    Generated files are upserted into the specified project.
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

    # Resize images aggressively to fit the AI provider's tiny context window.
    # qwen2.5-vl-7b has only 8192 tokens total. Base64 adds ~33% overhead.
    # We use JPEG quality 30 at 150px max to keep the payload small.
    if HAS_PIL:
        try:
            img = PILImage.open(io.BytesIO(raw_bytes))
            w, h = img.size
            max_dim = 150
            if w > max_dim or h > max_dim:
                ratio = max_dim / max(w, h)
                new_w, new_h = int(w * ratio), int(h * ratio)
                img = img.resize((new_w, new_h), PILImage.LANCZOS)
            # Convert to RGB (JPEG doesn't support RGBA) and save as low-quality JPEG
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=30, optimize=True)
            raw_bytes = buf.getvalue()
            logger.info("Resized upload image: %dx%d -> %dx%d (%d bytes, JPEG q30)", w, h, new_w, new_h, len(raw_bytes))
        except Exception as e:
            logger.warning("Failed to resize upload image, sending original: %s", e)

    # Validate project exists and user has access
    project = await _service.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id is not None and project.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Log which provider/model is handling this request
    logger.info("Design upload using model: %s (URL: %s)", getattr(_provider, '_model', 'unknown'), getattr(_provider, '_target_url', 'unknown'))

    # Build the design prompt with base64-encoded image
    b64_data = base64.b64encode(raw_bytes).decode("ascii")
    mime_type = file.content_type or "image/png"
    data_uri = f"data:{mime_type};base64,{b64_data}"

    user_prompt = (
        f"Here is a design image to convert to code.\n"
        f"Filename: {file.filename or 'design'}\n"
        f"Type: {mime_type}\n"
        f"Size: {len(raw_bytes)} bytes\n"
    )
    if prompt:
        user_prompt += f"\nAdditional instructions from the user: {prompt}\n"
    user_prompt += f"\nDesign image (data URI):\n{data_uri}"

    # Generate code from the design image
    try:
        message, files = await _provider.generate(
            user_prompt,
            system_prompt_override=_DESIGN_UPLOAD_SYSTEM_PROMPT,
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
    user_message = user_prompt[:50000] + "\n\n[design prompt truncated]" if len(user_prompt) > 50000 else user_prompt
    await _service.save_chat_message(project_id, "user", user_message)
    await _service.save_chat_message(project_id, "assistant", message, files)

    return GenerateResponse(
        project_id=project_id,
        project_name=project.name,
        message=message,
        files=files,
    )
