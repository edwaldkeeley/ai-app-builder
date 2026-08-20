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
    ts = "typescript"
    tsx = "tsx"
    jsx = "jsx"
    json = "json"
    python = "python"
    markdown = "markdown"
    svg = "svg"
    other = "other"


class Framework(str, Enum):
    vanilla = "vanilla"
    react = "react"


# ── Project ────────────────────────────────────────────────


class ProjectFile(BaseModel):
    """A single file within a sandbox project."""

    path: str = Field(..., max_length=512, description="Relative path, e.g. 'index.html' or 'src/app.js'")
    content: str = Field("", max_length=1_000_000, description="File content (max 1MB)")
    file_type: FileType = FileType.other


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="Human-readable project name")
    description: str = ""
    framework: Framework = Framework.vanilla
    template: str | None = Field(None, max_length=64, description="Template name from the gallery; replaces boilerplate")


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, max_length=128)
    description: str | None = None
    framework: Framework | None = None


class Project(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.idle
    framework: Framework = Framework.vanilla
    user_id: UUID | None = None
    files: list[ProjectFile] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectSummary(BaseModel):
    """Lightweight representation used in list endpoints."""

    id: UUID
    name: str
    description: str
    status: ProjectStatus
    framework: Framework = Framework.vanilla
    user_id: UUID | None = None
    file_count: int = 0
    created_at: datetime
    updated_at: datetime


# ── Sandbox ────────────────────────────────────────────────


class SandboxFileUpdate(BaseModel):
    """Payload to upsert a file in the sandbox."""

    path: str = Field(..., max_length=512)
    content: str = Field(..., max_length=1_000_000)


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
    framework: Framework = Framework.vanilla


class GenerateResponse(BaseModel):
    """Response after AI generation."""

    project_id: UUID
    project_name: str
    message: str = ""
    files: list[ProjectFile] = []



# ── Figma ──────────────────────────────────────────────────


class FigmaUrlImportRequest(BaseModel):
    """Request to import a Figma file by URL or file key."""

    figma_url: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Figma file URL (e.g. https://www.figma.com/file/KEY/name) or bare file key",
    )
    access_token: str = Field(
        ...,
        min_length=1,
        description="Figma personal access token. Generate one at https://www.figma.com/settings",
    )
    force_refresh: bool = Field(
        default=False,
        description="If true, bypass the cache and fetch fresh data from Figma API",
    )





class FigmaDebugPromptResponse(BaseModel):
    """Response for the Figma debug-prompt endpoint (no AI call)."""

    figma_file_name: str = Field("", description="Figma file name from the API")
    figma_file_key: str = Field("", description="Extracted Figma file key")
    tree_node_count: int = Field(0, description="Total nodes walked across all canvases")
    tree_capped: bool = Field(False, description="Whether the tree summary was truncated at 100k chars")
    filtered_json_size: int = Field(0, description="Size of filtered Figma JSON before truncation")
    filtered_json_capped: bool = Field(False, description="Whether the JSON was truncated at 40k chars")
    total_chars: int = Field(0, description="Total prompt character count")
    estimated_tokens: int = Field(0, description="Estimated tokens (chars // 3)")
    canvas_info: list[dict] = Field(default_factory=list, description="Per-canvas type/dimensions/node_count")
    prompt_text: str = Field("", description="The full prompt that would be sent to the AI")


# ── Chat ────────────────────────────────────────────────────


class ChatMessageSchema(BaseModel):
    """A single chat message in a project conversation."""

    id: int | None = None
    project_id: UUID
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=100_000)
    files: list[ProjectFile] = []
    created_at: datetime | None = None


# ── User Settings ────────────────────────────────────────────


class UpdateUserRequest(BaseModel):
    """Request to update user profile fields."""

    username: str | None = Field(None, min_length=1, max_length=128)
    email: str | None = Field(None, max_length=255)


class ChangePasswordRequest(BaseModel):
    """Request to change the user's password."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)
