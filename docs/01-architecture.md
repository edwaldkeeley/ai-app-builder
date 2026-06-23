# Architecture Overview

## High-Level Design

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Tab      │  │ Monaco   │  │ Live     │  │ Download│ │
│  │ Explorer │  │ Editor   │  │ Canvas   │  │ ZIP     │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Design Upload / Prompt Input / Figma Import UI  │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP / WebSocket
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend (Python)                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │ AI       │  │ Figma    │  │ Sandbox  │  │ File    │ │
│  │ Engine   │  │ OAuth    │  │ Executor │  │ Manager │ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│  ┌──────────────────────────────────────────────────┐   │
│  │  ZIP Export / Project Persistence                │   │
│  └──────────────────────┬───────────────────────────┘   │
│                         │                               │
│  ┌──────────────────────▼───────────────────────────┐   │
│  │  PostgreSQL (raw SQL via asyncpg)                │   │
│  │  ┌────────────────┐  ┌────────────────┐          │   │
│  │  │  projects      │  │  files         │          │   │
│  │  │  (UUID PK)     │◄─┤  (FK CASCADE)  │          │   │
│  │  └────────────────┘  └────────────────┘          │   │
│  │  ┌──────────────────────────────────────────┐    │   │
│  │  │  schema_migrations (append-only tracking) │    │   │
│  │  └──────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────┘
```

## Layers

### Frontend (Next.js / React)
- **TabExplorer** — file tree sidebar with open-file tabs
- **MonacoEditor** — VS Code-quality code editor
- **LiveCanvas** — sandboxed iframe that renders the project's HTML/CSS/JS
- **AIPromptBar** — text input for prompt-to-app generation
- **DesignUpload** — image upload for design-to-HTML conversion
- **FigmaImport** — OAuth flow + file picker for Figma imports
- **DownloadButton** — triggers ZIP export from the backend

### Backend (FastAPI / Python)
- **Routers** — REST endpoints grouped by domain (projects, sandbox, figma, ai, export)
- **Services** — business logic (project CRUD, AI engine, Figma API client, ZIP builder)
- **Models** — Pydantic schemas for request/response validation

### Communication
- **REST** — standard CRUD and file operations
- **WebSocket** (future) — streaming AI generation results to the editor/canvas in real-time

## Data Flow

```
User Prompt ──► AIPromptBar ──► POST /api/ai/generate ──► AI Engine ──► Files
                                                              │
                                                              ▼
User sees ◄── Live Canvas ◄── WebSocket stream ◄─────── Generated Code
```

## Database

PostgreSQL is the persistent store, accessed via raw SQL through the `asyncpg` driver (no ORM).

### Schema

Two core tables:

- **`projects`** — `id` (UUID PK), `name`, `description`, `status`, `created_at`, `updated_at`
- **`files`** — `id` (SERIAL PK), `project_id` (FK → projects, CASCADE), `path`, `content`, `file_type`, `created_at`, `updated_at`; `UNIQUE(project_id, path)`

A separate `files` table is used instead of a JSONB column because the sandbox performs frequent single-file upserts and deletes. With a normalized design, these are atomic single-row operations. A JSONB column would require reading and rewriting the entire blob on every file change, risking data races under concurrent edits.

### Migrations

Migrations are **append-only** — existing migration files are never modified. New schema changes are added as new numbered `.sql` files:

```
backend/app/db/migrations/
├── 001_create_tables.sql
├── 002_...
└── ...
```

A `schema_migrations` table tracks which migrations have been applied. Each migration runs in a transaction with its tracking insert, guaranteeing exactly-once execution. The runner checks this table on startup and skips already-applied migrations.

### Connection Management

A module-level `asyncpg` connection pool is initialized during the FastAPI lifespan startup and closed on shutdown. The pool is configured via environment variables (`DATABASE_URL`, `DATABASE_POOL_MIN_SIZE`, `DATABASE_POOL_MAX_SIZE`).

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Editor | Monaco | Same engine as VS Code; rich API, syntax highlighting, multi-cursor |
| Canvas | Sandboxed iframe | True browser rendering, isolated from the app's own DOM |
| Backend framework | FastAPI | Async, auto-docs, Pydantic integration, fast |
| AI interface | Abstract base class | Swap models without changing business logic |
| Database | PostgreSQL (raw SQL) | Reliable, normalized, append-only migrations via `asyncpg` |
| Storage | Separate `files` table | Normalized design — single-row file ops, no data races on concurrent edits |
