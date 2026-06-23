"""REST endpoints for AI-powered code generation."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import GenerateResponse, ProjectCreate, PromptRequest
from app.services.ai_service import BaseAIProvider
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/ai", tags=["ai"])

_provider: BaseAIProvider | None = None
_service: ProjectService | None = None


def set_dependencies(provider: BaseAIProvider, service: ProjectService) -> None:
    global _provider, _service
    _provider = provider
    _service = service


@router.post("/generate", response_model=GenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate(body: PromptRequest):
    """Generate code from a text prompt using the configured AI provider.

    If ``project_id`` is provided, the generated files are added to that
    project.  Otherwise a new project is created.
    """
    if _provider is None or _service is None:
        raise HTTPException(
            status_code=503,
            detail="AI provider not initialised. Set TARGET_URL, JWT_TOKEN, and MODEL.",
        )

    try:
        message, files = await _provider.generate(body.prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if body.project_id:
        # Update existing project
        project = await _service.get(body.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")

        for f in files:
            await _service.upsert_file(project.id, f.path, f.content)

        project_name = project.name
        project_id = project.id
    else:
        # Create new project
        name = body.prompt[:120].strip()
        project = await _service.create(
            ProjectCreate(
                name=name,
                description=f"Generated from: {body.prompt[:200]}",
            )
        )
        project_id = project.id
        project_name = project.name

        for f in files:
            await _service.upsert_file(project_id, f.path, f.content)

    return GenerateResponse(
        project_id=project_id,
        project_name=project_name,
        message=message,
        files=files,
    )
