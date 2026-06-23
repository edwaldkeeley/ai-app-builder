# AI Design Sandbox — CLAUDE.md

> **Workflow:** After every design discussion, I auto-update this file and the memory files to reflect decisions made. If something seems out of date, it probably is — just ask.

## Project Overview

AI-powered design-to-code platform. Users describe what they want in natural language, and the platform generates a fully editable web project with a live preview and code editor.

- **Phase 1 (Complete)**: Backend — FastAPI with project CRUD, sandbox file operations, PostgreSQL persistence via raw SQL, AI engine with OpenAI-compatible HTTP provider.
- **Phase 2 (In Progress)**: Frontend — ChatGPT-inspired layout with centered chat landing page, Monaco editor, live canvas iframe preview, sidebar toggles between project list and chat.

## Architecture

```
Next.js Frontend (port 3000)  ←→  FastAPI Backend (port 8000)
                                           │
                               PostgreSQL 16 (port 5432)
```

Monorepo with two packages (no monorepo tool — `run.py` spawns subprocesses, Docker Compose for containerized workflow).

## Prerequisites

- **Docker**: `docker compose up --build` (recommended)
- **Local dev**: PostgreSQL 14+ running locally, `createdb ai_design_sandbox`

## Quick Start

### Docker (recommended)

```bash
docker compose up --build
```

### Local Dev

```bash
# Backend
cd backend && pip install -r requirements.txt && uvicorn main:app --reload

# Frontend
cd frontend && npm install && npm run dev

# Both
python run.py --all
```

API docs: `http://localhost:8000/docs`

## Key Files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI entry point |
| `backend/app/config.py` | Pydantic Settings (env-driven), requires TARGET_URL/JWT_TOKEN/MODEL for AI |
| `backend/app/models/schemas.py` | All Pydantic request/response models |
| `backend/app/routers/projects.py` | CRUD: `/api/projects` |
| `backend/app/routers/sandbox.py` | File ops: `/api/sandbox` |
| `backend/app/routers/ai.py` | `POST /api/ai/generate` — AI code generation |
| `backend/app/routers/chat.py` | `GET/POST /api/projects/{id}/chat` — Chat message persistence |
| `backend/app/services/project_service.py` | PostgreSQL-backed project + file + chat message management (asyncpg) |
| `backend/app/services/ai_service.py` | Abstract BaseAIProvider + HttpAIProvider (OpenAI-compatible) |
| `backend/app/db/database.py` | asyncpg pool manager + migration runner |
| `backend/app/db/migrations/` | Append-only SQL migration files |
| `frontend/src/app/page.tsx` | Main page — orchestrates sidebar, main content, chat state, API calls |
| `frontend/src/app/components/Sidebar.tsx` | Collapsible sidebar — project list OR chat panel (toggles based on mode) |
| `frontend/src/app/components/MainContent.tsx` | Centered chat landing page OR Editor + Canvas split |
| `frontend/src/app/components/ChatPanel.tsx` | Chat message list with markdown rendering + integrated prompt input |
| `frontend/src/app/components/EditorPane.tsx` | Monaco editor with file tabs |
| `frontend/src/app/components/LiveCanvas.tsx` | Sandboxed iframe preview |
| `frontend/src/app/lib/api.ts` | Typed API client |
| `frontend/src/app/lib/types.ts` | Shared TypeScript interfaces |
| `docker-compose.yml` | 3-service Compose definition (backend, frontend, db) |
| `backend/Dockerfile` | Python 3.12-slim image for FastAPI |
| `frontend/Dockerfile` | Node 22-alpine image for Next.js |
| `run.py` | One-command launcher |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/projects/` | List all projects |
| POST | `/api/projects/` | Create project (with boilerplate files) |
| GET | `/api/projects/{id}` | Get project details + files |
| PATCH | `/api/projects/{id}` | Update name/description |
| DELETE | `/api/projects/{id}` | Delete project |
| GET | `/api/sandbox/{id}` | Get full sandbox state |
| PUT | `/api/sandbox/{id}/files` | Create/update a file |
| DELETE | `/api/sandbox/{id}/files?path=...` | Delete a file |
| POST | `/api/ai/generate` | Generate code from prompt (returns message + files) |
| GET | `/api/projects/{id}/chat` | Get chat messages for a project |
| POST | `/api/projects/{id}/chat` | Save a chat message |

## Data Model

**Project**: `id` (UUID), `name`, `description`, `status` (idle/generating/error), `files` (list of {path, content, file_type}), `created_at`, `updated_at`.

**GenerateResponse**: `project_id`, `project_name`, `message` (AI conversational response), `files` (generated files).

**ChatMessage**: `id`, `project_id`, `role` (user/assistant), `content`, `files` (JSONB), `created_at`.

New projects get boilerplate: `index.html`, `style.css`, `script.js`.

## Coding Conventions

- **Backend**: FastAPI + Pydantic v2 (use `model_dump()`, `model_validate()`). Singleton service pattern injected into `app.state`. UUIDs as strings.
- **Database**: Raw SQL via `asyncpg` (no ORM). Append-only migrations in `app/db/migrations/`. Separate `files` table (not JSONB) for atomic single-file operations. JSONB columns require `json.dumps()` for inserts.
- **AI**: Abstract BaseAIProvider + HttpAIProvider. OpenAI-compatible chat format (messages array). JWT bearer auth. Returns `(message, list[ProjectFile])` tuple. Parses `{"message": "...", "files": [...]}` from `choices[0].message.content`. System prompt tells model to preserve indentation/line breaks and use standard filenames.
- **Frontend**: Next.js 16 App Router, React 19, Tailwind CSS v4 syntax (`@import "tailwindcss"`, `@theme inline`), TypeScript, Monaco Editor, react-markdown + remark-gfm for AI message rendering.
- **File type inference**: From extension — `.html`, `.css`, `.js`, `.json`, `.py`, or `other`.
- **No tests yet** — add them when implementing new features.
- **Root `.gitignore`** exists — excludes `.env`, `__pycache__/`, `node_modules/`, `.next/`, etc.

## Environment Variables (.env at project root)

The `.env` file lives at the **project root** (`./.env`) — not in `backend/`. Docker Compose auto-reads it from the root. The backend's Pydantic Settings resolves the path absolutely from `config.py`.

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | "AI Design Sandbox" | App title |
| `DEBUG` | `true` | Debug mode |
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `8000` | Bind port |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/ai_design_sandbox` | PostgreSQL connection string (hardcoded in docker-compose.yml) |
| `DATABASE_POOL_MIN_SIZE` | `2` | Minimum pool connections |
| `DATABASE_POOL_MAX_SIZE` | `10` | Maximum pool connections |
| `TARGET_URL` | (required for AI) | AI provider API endpoint (OpenAI-compatible) |
| `JWT_TOKEN` | (required for AI) | AI provider JWT bearer token |
| `MODEL` | (required for AI) | AI model identifier |
| `FIGMA_CLIENT_ID` | (empty) | Figma OAuth |
| `FIGMA_CLIENT_SECRET` | (empty) | Figma OAuth |
| `FIGMA_REDIRECT_URI` | `http://localhost:8000/api/figma/callback` | Figma OAuth |

## Bugs Fixed

1. **`backend/app/routers/ai.py`** — Replaced `type("FakeCreate", ...)` with proper `ProjectCreate(name=..., description=...)`.
2. **`backend/app/services/ai_service.py`** — Made JSON extraction robust: finds first `{`/last `}` instead of relying on regex stripping.
3. **`backend/app/config.py`** — Changed `env_file` path from relative `".env"` to absolute path resolving to project root.
4. **`.env` moved** from `backend/` to project root so Docker Compose can read it.
5. **Root `.gitignore`** created.
6. **Git history rewritten** — removed `backend/.env` from all commits. Pushed to new repo `ai-app-builder`.
7. **Nested button bug** — `Sidebar.tsx` had `<button>` inside `<button>`, causing hydration errors. Changed to `<div role="button">`.
8. **Chat persistence JSONB encoding** — `project_service.py` was passing a Python list to asyncpg's JSONB column instead of a JSON string. Fixed with `json.dumps()`.
9. **AI output formatting** — System prompt said "NO markdown formatting" which some models interpreted as "remove all newlines/indentation." Updated to explicitly tell the model to preserve formatting and use standard filenames.

## Features Added

1. **AI conversational responses** — `GenerateResponse` now includes a `message` field with the AI's explanation.
2. **Chat panel in sidebar** — Sidebar toggles between project list and chat panel with markdown-rendered AI messages.
3. **Centered chat landing page** — ChatGPT-style landing page when no project is selected. Sending a prompt auto-creates a project.
4. **Chat persistence** — `chat_messages` table + API endpoints. Messages survive page refresh.
5. **No auto-select** — App starts with centered chat landing, no project auto-selected.
6. **Auto-create project on prompt** — Sending a prompt from the landing page creates a project automatically.

## Planned Features (not yet implemented)

- WebSocket streaming for AI generation
- Figma OAuth integration
- ZIP export endpoint
- File saving to backend (edits are in-memory only)
- Add/delete files from UI
- Design Upload, Figma Import, Download Button

## Dependencies

**Backend**: fastapi, uvicorn, pydantic, pydantic-settings, python-multipart, httpx (AI provider calls), python-dotenv, asyncpg

**Frontend**: next, react, react-dom, tailwindcss, @tailwindcss/postcss, typescript, eslint, eslint-config-next, @monaco-editor/react, react-markdown, remark-gfm
