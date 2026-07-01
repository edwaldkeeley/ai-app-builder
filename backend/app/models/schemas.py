"""Pydantic schemas for request/response validation."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────


class ProjectStatus(str, Enum):
    idle = "idle"
    generating = "generating"
    error = "error"


class FileType(str, Enum):
    html = "html"
    css = "css"
    js = "javascript"
    json = "json"
    python = "python"
    other = "other"


# ── Project ────────────────────────────────────────────────


class ProjectFile(BaseModel):
    """A single file within a sandbox project."""

    path: str = Field(..., max_length=512, description="Relative path, e.g. 'index.html' or 'src/app.js'")
    content: str = ""
    file_type: FileType = FileType.other


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Human-readable project name")
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, max_length=128)
    description: str | None = None


class Project(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.idle
    files: list[ProjectFile] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectSummary(BaseModel):
    """Lightweight representation used in list endpoints."""

    id: UUID
    name: str
    description: str
    status: ProjectStatus
    file_count: int = 0
    created_at: datetime
    updated_at: datetime


# ── Sandbox ────────────────────────────────────────────────


class SandboxFileUpdate(BaseModel):
    """Payload to upsert a file in the sandbox."""

    path: str = Field(..., max_length=512)
    content: str


class SandboxState(BaseModel):
    """Full snapshot of a sandbox workspace."""

    project_id: UUID
    files: list[ProjectFile]
    active_file_path: str | None = None


# ── AI / Generation ────────────────────────────────────────


class PromptRequest(BaseModel):
    """Request body for prompt-based generation."""

    prompt: str = Field(..., min_length=1, max_length=10_000)
    project_id: UUID | None = None


class GenerateResponse(BaseModel):
    """Response after AI generation."""

    project_id: UUID
    project_name: str
    message: str = ""
    files: list[ProjectFile] = []


class DesignUploadResponse(BaseModel):
    """Response after uploading a design image for conversion."""

    project_id: UUID
    message: str
    files: list[ProjectFile] = []


# ── Figma ──────────────────────────────────────────────────


class FigmaImportRequest(BaseModel):
    """Request to import a Figma file."""

    figma_file_key: str = Field(..., min_length=1, description="Figma file key from the URL")
    page_name: str | None = None


class FigmaUrlImportRequest(BaseModel):
    """Request to import a Figma file by URL or file key."""

    figma_url: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Figma file URL (e.g. https://www.figma.com/file/KEY/name) or bare file key",
    )
    access_token: str | None = Field(
        None,
        description="Figma personal access token (optional if OAuth-connected)",
    )


class FigmaAuthUrl(BaseModel):
    url: str


class FigmaFile(BaseModel):
    """A Figma file as returned by the file listing endpoint."""

    key: str
    name: str
    last_modified: str | None = None
    thumbnail_url: str | None = None




# ── Export ─────────────────────────────────────────────────


class ExportResponse(BaseModel):
    """Response containing the ZIP download URL."""

    download_url: str
    project_id: UUID


# ── Chat ────────────────────────────────────────────────────


class ChatMessageSchema(BaseModel):
    """A single chat message in a project conversation."""

    id: int | None = None
    project_id: UUID
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=100_000)
    files: list[ProjectFile] = []
    created_at: datetime | None = None
