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
    user_id: UUID | None = None
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


# ── Design Upload (Two-Stage Pipeline) ──────────────────────


class DesignElement(BaseModel):
    """A single visual element in a design spec."""

    type: str = Field(..., description="Element type: heading, paragraph, button, image, icon, card, input, nav, container, divider, list, video, map, form, badge, avatar, progress, chart, table, modal, tooltip, accordion, carousel, tabs, breadcrumb, pagination, sidebar, header, footer, hero, section, wrapper")
    text: str = ""
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    color: str = ""
    bg: str = ""
    font_family: str = ""
    font_size: int = 0
    font_weight: int = 0
    text_align: str = "left"
    border_radius: int = 0
    opacity: float = 1.0
    children: list[DesignElement] = []


# Rebuild DesignElement to resolve the self-referencing forward reference
DesignElement.model_rebuild()


class DesignSection(BaseModel):
    """A section of the design (hero, features, footer, etc.)."""

    type: str = Field(..., description="Section type: hero, features, pricing, testimonials, footer, header, sidebar, content, form, gallery, stats, cta, faq, contact, team, blog, portfolio, logo-cloud, comparison, timeline, steps, banner, popup, splash, dashboard, settings, profile, search, cart, checkout, product, listing, detail, landing")
    x: int = 0
    y: int = 0
    w: int = 0
    h: int = 0
    bg: str = ""
    columns: int = 1
    elements: list[DesignElement] = []


class DesignSpec(BaseModel):
    """Structured design specification produced by the vision model.

    This is the intermediate output of Stage 1 (vision model analysis).
    Stage 2 (main code generation model) consumes this to produce full HTML/CSS/JS.
    """

    layout: str = Field("", description="Overall layout type: centered single column, full-width, sidebar left, sidebar right, grid, dashboard, landing page, application, marketing page, blog, e-commerce, portfolio, documentation, landing, splash, coming-soon, error-page, minimal, magazine, card-based, split-screen, overlapping, asymmetric, experimental")
    width: int = 0
    colors: dict[str, str] = Field(default_factory=dict, description="Color palette: keys like bg, primary, secondary, text, accent, muted, success, warning, error, info, border, surface")
    fonts: list[dict[str, Any]] = Field(default_factory=list, description="Font families and sizes used")
    sections: list[DesignSection] = []


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
