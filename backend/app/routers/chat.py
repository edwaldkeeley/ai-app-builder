"""REST endpoints for chat message history."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.models.schemas import ChatMessageSchema, ProjectFile
from app.routers.dependencies import get_current_user
from app.routers.projects import get_service

router = APIRouter(prefix="/api/projects", tags=["chat"])


class SaveChatMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=100_000)
    files: list[ProjectFile] = []


@router.get("/{project_id}/chat", response_model=list[ChatMessageSchema])
async def get_chat_messages(project_id: UUID, current_user: dict = Depends(get_current_user)):
    """Get all chat messages for a project, ordered by creation time."""
    project = await get_service().get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id is not None and project.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return await get_service().get_chat_messages(project_id)


@router.post("/{project_id}/chat", response_model=ChatMessageSchema, status_code=201)
async def save_chat_message(project_id: UUID, body: SaveChatMessageRequest, current_user: dict = Depends(get_current_user)):
    """Save a new chat message for a project."""
    project = await get_service().get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.user_id is not None and project.user_id != current_user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    return await get_service().save_chat_message(
        project_id=project_id,
        role=body.role,
        content=body.content,
        files=body.files,
    )
