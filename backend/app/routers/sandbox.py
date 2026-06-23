"""Endpoints for the live sandbox — file editing and state retrieval."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.models.schemas import ProjectFile, SandboxFileUpdate, SandboxState
from app.routers.projects import get_service

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])


@router.get("/{project_id}", response_model=SandboxState)
async def get_sandbox_state(project_id: UUID):
    """Return the full sandbox state for a project (all files + active file)."""
    project = await get_service().get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return SandboxState(
        project_id=project.id,
        files=project.files,
        active_file_path=project.files[0].path if project.files else None,
    )


@router.put("/{project_id}/files", response_model=ProjectFile)
async def upsert_file(project_id: UUID, body: SandboxFileUpdate):
    """Create or update a single file in the sandbox."""
    result = await get_service().upsert_file(project_id, body.path, body.content)
    if result is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return result


@router.delete("/{project_id}/files", status_code=204)
async def delete_file(project_id: UUID, path: str):
    """Delete a file from the sandbox. Pass ``?path=...`` as a query param."""
    if not await get_service().delete_file(project_id, path):
        raise HTTPException(status_code=404, detail="Project or file not found")
