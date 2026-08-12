# AI Design Sandbox — CLAUDE.md

> **Workflow:** After every design discussion, I auto-update this file and the memory files to reflect decisions made. If something seems out of date, it probably is — just ask.

## Project Overview

AI-powered design-to-code platform. Users describe what they want in natural language, and the platform generates a fully editable web project with a live preview and code editor.

All three phases are complete: backend (FastAPI + PostgreSQL), frontend (Next.js + Monaco + live preview), and features (Figma import, design upload, auth, settings, React support, UI polish).

## Architecture

```
Next.js Frontend (port 3000)  ←→  FastAPI Backend (port 8000)
                                           │
                               PostgreSQL 16 (port 5432)
```

Monorepo with two packages — `run.py` spawns subprocesses, Docker Compose for containerized workflow.

## Quick Start

```bash
# Docker (recommended)
docker compose up --build

# Local dev
cd backend && pip install -r requirements.txt && uvicorn main:app --reload
cd frontend && npm install && npm run dev
python run.py --all
```

API docs: `http://localhost:8000/docs`

## Key Files

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI entry point |
| `backend/app/config.py` | Pydantic Settings (env-driven) |
| `backend/app/models/schemas.py` | All Pydantic request/response models |
| `backend/app/routers/projects.py` | CRUD: `/api/projects` |
| `backend/app/routers/sandbox.py` | File ops: `/api/sandbox` |
| `backend/app/routers/ai.py` | `POST /api/ai/generate` — AI code generation |
| `backend/app/routers/chat.py` | Chat message persistence |
| `backend/app/routers/figma.py` | Figma URL import endpoint |
| `backend/app/routers/upload.py` | Design image upload + two-stage vision pipeline |
| `backend/app/routers/auth.py` | Auth endpoints |
| `backend/app/services/project_service.py` | PostgreSQL-backed project + file + chat management (asyncpg) |
| `backend/app/services/ai_service.py` | Abstract BaseAIProvider + HttpAIProvider + StreamingHttpAIProvider |
| `backend/app/services/prompts.py` | All system prompt templates (vanilla, React, design upload, Figma) |
| `backend/app/services/json_parser.py` | JSON/markdown parsing with repair strategies for LLM output |
| `backend/app/services/file_validator.py` | React import fixing + generated file validation |
| `backend/app/services/figma_service.py` | Figma REST API client + design prompt builder |
| `backend/app/services/figma_service.py` | Figma REST API client + design prompt builder |
| `backend/app/services/auth_service.py` | JWT + password hashing + user CRUD |
| `backend/app/db/database.py` | asyncpg pool manager + migration runner |
| `backend/app/db/migrations/` | Append-only SQL migration files |
| `frontend/src/app/page.tsx` | Main page — orchestrates sidebar, main content, chat, API calls |
| `frontend/src/app/components/` | All React components (Sidebar, ChatPanel, EditorPane, LiveCanvas, FileExplorer, etc.) |
| `frontend/src/app/contexts/` | AuthContext, ThemeContext |
| `frontend/src/app/hooks/` | useProjects, useChat, useFileSave, useKeyboardShortcuts |
| `frontend/src/app/lib/` | API client, types, UI primitives, file icons |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Health check |
| GET/POST | `/api/projects/` | List / Create projects |
| GET/PATCH/DELETE | `/api/projects/{id}` | Get / Update / Delete project |
| GET | `/api/sandbox/{id}` | Get full sandbox state |
| PUT/DELETE | `/api/sandbox/{id}/files` | Create/update / Delete a file |
| POST | `/api/ai/generate` | Generate code from prompt |
| POST | `/api/ai/ws/generate` | WebSocket — streaming AI code generation |
| GET/POST | `/api/projects/{id}/chat` | Get / Save chat messages |
| GET | `/api/projects/{id}/export` | Download project as ZIP |
| POST | `/api/projects/{id}/upload-design` | Upload design image → AI generates code |
| POST | `/api/figma/import-url` | Import Figma design by URL + personal access token |
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login, returns JWT |
| GET/PATCH/DELETE | `/api/auth/me` | Profile CRUD |
| POST | `/api/auth/me/change-password` | Change password |

## Data Model

**Project**: `id` (UUID), `name`, `description`, `status` (idle/generating/error), `framework` (vanilla/react), `user_id` (UUID, FK to users), `files` (list of {path, content, file_type}), `created_at`, `updated_at`.

**User**: `id` (UUID), `username` (unique), `email` (unique), `password_hash`, `theme` (light/dark), `created_at`, `updated_at`.

**ChatMessage**: `id`, `project_id`, `role` (user/assistant), `content`, `files` (JSONB), `created_at`.

New projects get boilerplate: `index.html`, `style.css`, `script.js` (vanilla) or `App.jsx`, `style.css` (React).

## Coding Conventions

- **Backend**: FastAPI + Pydantic v2 (`model_dump()`, `model_validate()`). Singleton service pattern injected into `app.state`. UUIDs as strings.
- **Database**: Raw SQL via `asyncpg` (no ORM). Append-only migrations in `app/db/migrations/`. Separate `files` table (not JSONB). JSONB columns require `json.dumps()` for inserts.
- **AI**: Abstract BaseAIProvider + HttpAIProvider. OpenAI-compatible chat format. JWT bearer auth. Returns `(message, list[ProjectFile])` tuple. System prompt tells model to preserve formatting and use standard filenames.
- **Figma**: URL import with personal access token (`X-Figma-Token` header). No OAuth. File key extracted from URL.
- **Frontend**: Next.js 16 App Router, React 19, Tailwind CSS v4 (`@import "tailwindcss"`, `@theme inline`), TypeScript, Monaco Editor, react-markdown + remark-gfm.
- **File type inference**: From extension — `.html`, `.css`, `.js`, `.json`, `.py`, or `other`.
- **Tests**: 100 frontend (Jest) + 207 backend (pytest) — `cd frontend && npx jest` or `cd backend && python -m pytest`.
- **Root `.gitignore`** exists — excludes `.env`, `__pycache__/`, `node_modules/`, `.next/`, etc.
- **Zero lint/type errors** — `npx tsc --noEmit` and `npx eslint src/` both pass clean. Maintain this standard before committing.

## Environment Variables (`.env` at project root)

| Variable | Default | Description |
|---|---|---|
| `APP_NAME` | "AI Design Sandbox" | App title |
| `DEBUG` | `true` | Debug mode |
| `HOST` / `PORT` | `127.0.0.1:8000` | Bind address |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/ai_design_sandbox` | PostgreSQL connection |
| `TARGET_URL` | (required) | AI provider API endpoint (OpenAI-compatible) |
| `JWT_TOKEN` | (required) | AI provider JWT bearer token |
| `MODEL` | (required) | AI model identifier |
| `MAX_TOKENS` | `16384` | Max output tokens |
| `TIMEOUT_SECONDS` | `600` | AI provider request timeout |
| `DESIGN_UPLOAD_TARGET_URL` | (falls back to TARGET_URL) | Optional separate endpoint for vision model |
| `DESIGN_UPLOAD_JWT_TOKEN` | (falls back to JWT_TOKEN) | Optional separate JWT for vision |
| `DESIGN_UPLOAD_MODEL` | (falls back to MODEL) | Optional separate model for vision |
| `MAX_UPLOAD_SIZE_MB` | `10` | Max design upload file size |
