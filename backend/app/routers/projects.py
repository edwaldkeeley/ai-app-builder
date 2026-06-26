"""REST endpoints for project CRUD."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.models.schemas import Project, ProjectCreate, ProjectSummary, ProjectUpdate
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
async def list_projects():
    return await get_service().list_all()


@router.post("/", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(body: ProjectCreate):
    return await get_service().create(body)


@router.get("/{project_id}", response_model=Project)
async def get_project(project_id: UUID):
    project = await get_service().get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=Project)
async def update_project(project_id: UUID, body: ProjectUpdate):
    project = await get_service().update(project_id, body)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: UUID):
    if not await get_service().delete(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
