"""REST endpoints for project CRUD."""

from __future__ import annotations

import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.models.schemas import Project, ProjectCreate, ProjectSummary, ProjectUpdate
from app.routers.dependencies import get_current_user
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])

_service: ProjectService | None = None


def set_project_service(svc: ProjectService) -> None:
    global _service
    _service = svc


def get_service() -> ProjectService:
    if _service is None:
        raise RuntimeError("ProjectService not initialised")
    return _service


# ── Endpoints ──────────────────────────────────────────────


@router.get("/", response_model=list[ProjectSummary])
async def list_projects(current_user: dict = Depends(get_current_user)):
    return await get_service().list_all(user_id=current_user["id"])


@router.post("/", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate, current_user: dict = Depends(get_current_user)):
    return await get_service().create(body, user_id=current_user["id"])


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: UUID, current_user: dict = Depends(get_current_user)):
    project = await get_service().get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id is not None and project.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return project


@router.patch("/{project_id}", response_model=Project)
async def update_project(project_id: UUID, body: ProjectUpdate, current_user: dict = Depends(get_current_user)):
    project = await get_service().update(project_id, body)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id is not None and project.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID, current_user: dict = Depends(get_current_user)):
    project = await get_service().get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id is not None and project.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    if not await get_service().delete(project_id):
        raise HTTPException(status_code=404, detail="Project not found")


@router.get("/{project_id}/export")
async def export_project(project_id: UUID, current_user: dict = Depends(get_current_user)):
    """Download all project files as a ZIP archive."""
    svc = get_service()
    project = await svc.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id is not None and project.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    zip_bytes = await svc.export_as_zip(project_id)
    safe_name = re.sub(r"[^\w\-_\. ]", "_", project.name)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}.zip"',
            "Content-Length": str(len(zip_bytes)),
        },
    )
