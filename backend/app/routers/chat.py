"""REST endpoints for chat message history."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.schemas import ChatMessageSchema, ProjectFile
from app.routers.projects import get_service

router = APIRouter(prefix="/api/projects", tags=["chat"])


class SaveChatMessageRequest(BaseModel):
    role: str
    content: str
    files: list[ProjectFile] = []


@router.get("/{project_id}/chat", response_model=list[ChatMessageSchema])
async def get_chat_messages(project_id: UUID):
    """Get all chat messages for a project, ordered by creation time."""
    project = await get_service().get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return await get_service().get_chat_messages(project_id)


@router.post("/{project_id}/chat", response_model=ChatMessageSchema, status_code=201)
async def save_chat_message(project_id: UUID, body: SaveChatMessageRequest):
    """Save a new chat message for a project."""
    project = await get_service().get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return await get_service().save_chat_message(
        project_id=project_id,
        role=body.role,
        content=body.content,
        files=body.files,
    )
