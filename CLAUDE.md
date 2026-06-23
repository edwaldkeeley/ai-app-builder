# AI Design Sandbox — CLAUDE.md

> **Workflow:** After every design discussion, I auto-update this file and the memory files to reflect decisions made. If something seems out of date, it probably is — just ask.

## Project Overview

AI-powered design-to-code platform. Users describe what they want in natural language, and the platform generates a fully editable web project with a live preview and code editor.

- **Phase 1 (Complete)**: Backend — FastAPI with project CRUD, sandbox file operations, PostgreSQL persistence via raw SQL, AI engine with OpenAI-compatible HTTP provider.
- **Phase 2 (In Progress)**: Frontend — layout shell with ChatGPT-inspired design, Monaco editor, live canvas iframe preview, chat panel sidebar, project CRUD, AI prompt bar wired to backend.

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
| `backend/app/services/project_service.py` | PostgreSQL-backed project + file management (asyncpg) |
| `backend/app/services/ai_service.py` | Abstract BaseAIProvider + HttpAIProvider (OpenAI-compatible) |
| `backend/app/db/database.py` | asyncpg pool manager + migration runner |
| `backend/app/db/migrations/` | Append-only SQL migration files |
| `frontend/src/app/page.tsx` | Main page — orchestrates sidebar, editor, canvas, prompt bar |
| `frontend/src/app/components/Sidebar.tsx` | Collapsible sidebar — project list OR chat history |
| `frontend/src/app/components/MainContent.tsx` | Editor + canvas split view |
| `frontend/src/app/components/EditorPane.tsx` | Monaco editor with file tabs |
| `frontend/src/app/components/LiveCanvas.tsx` | Sandboxed iframe preview |
| `frontend/src/app/components/PromptBar.tsx` | Bottom-anchored AI prompt input |
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
| POST | `/api/ai/generate` | Generate code from prompt (requires TARGET_URL, JWT_TOKEN, MODEL) |

## Data Model

**Project**: `id` (UUID), `name`, `description`, `status` (idle/generating/error), `files` (list of {path, content, file_type}), `created_at`, `updated_at`.

New projects get boilerplate: `index.html`, `style.css`, `script.js`.

## Coding Conventions

- **Backend**: FastAPI + Pydantic v2 (use `model_dump()`, `model_validate()`). Singleton service pattern injected into `app.state`. UUIDs as strings.
- **Database**: Raw SQL via `asyncpg` (no ORM). Append-only migrations in `app/db/migrations/`. Separate `files` table (not JSONB) for atomic single-file operations.
- **AI**: Abstract BaseAIProvider + HttpAIProvider. OpenAI-compatible chat format (messages array). JWT bearer auth. Parses files from choices[0].message.content.
- **Frontend**: Next.js 16 App Router, React 19, Tailwind CSS v4 syntax (`@import "tailwindcss"`, `@theme inline`), TypeScript, Monaco Editor.
- **File type inference**: From extension — `.html`, `.css`, `.js`, `.json`, `.py`, or `other`.
- **No tests yet** — add them when implementing new features.
- **No root `.gitignore`** — only in `frontend/`.

## Environment Variables (.env at project root)

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

## Known Bugs (to fix)

1. **`backend/app/routers/ai.py` line 57** — Uses `type("FakeCreate", ...)` instead of proper `ProjectCreate(name=..., description=...)`. Fragile, bypasses Pydantic validation.
2. **`backend/app/services/ai_service.py`** — JSON parsing too brittle. If model returns extra text before/after JSON, parsing fails. Should find first `{`/last `}` instead.
3. **`backend/app/routers/ai.py`** — Multi-file upsert in update path has no transaction. Partial failure leaves inconsistent state.
4. **`backend/app/routers/ai.py`** — `project_name` variable could be undefined in some error paths.

## Planned Features (not yet implemented)

- WebSocket streaming for AI generation
- Figma OAuth integration
- ZIP export endpoint
- File saving to backend (edits are in-memory only)
- Add/delete files from UI
- Design Upload, Figma Import, Download Button

## Dependencies

**Backend**: fastapi, uvicorn, pydantic, pydantic-settings, python-multipart, httpx (AI provider calls), python-dotenv, asyncpg

**Frontend**: next, react, react-dom, tailwindcss, @tailwindcss/postcss, typescript, eslint, eslint-config-next, @monaco-editor/react
