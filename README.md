# AI Design Sandbox

An AI-powered design-to-code platform. Describe what you want in natural language, and the platform generates a fully editable web project with a live preview and code editor.

> **Status:** Phase 1 (Backend) ✅ & Phase 2 (Frontend) ✅ Complete — 44 bugs fixed, zero lint/type errors. Phase 3 (Figma, ZIP export, testing) pending.

## Features

- [x] **Backend API** — FastAPI with project CRUD, sandbox file management, PostgreSQL persistence
- [x] **AI Code Generation** — Natural language → full HTML/CSS/JS projects with streaming WebSocket output
- [x] **Chat Interface** — ChatGPT-style conversation with markdown-rendered AI responses
- [x] **Monaco Editor** — Full-featured code editor with syntax highlighting, undo history, model-based tab switching
- [x] **Live Preview** — Sandboxed iframe that renders generated HTML/CSS/JS in real-time
- [x] **File Explorer** — VS Code-style tree view with directory structure, file icons, rename/delete/new file
- [x] **View Modes** — Toggle between Preview, Code, and Split (50/50) layouts
- [x] **Chat Persistence** — Messages survive page refresh via PostgreSQL
- [x] **Auto-Save** — Debounced file saving to backend (800ms)
- [x] **WebSocket Streaming** — AI output streams character-by-character into chat and files in real-time
- [ ] **Figma Import** — OAuth flow to pull designs from Figma and convert to HTML
- [ ] **ZIP Export** — Download your project as a zip file
- [ ] **Design Upload** — Upload an image and have AI convert it to code
- [ ] **Tests** — Unit and integration test suite

## Quick Start

### Option A: Docker (recommended)

Requires Docker Desktop.

```bash
# Build and start all services
docker compose up --build
```

The app will be available at:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

### Option B: Local Dev

Requires Python 3.10+, Node.js 18+, and PostgreSQL 14+ running locally.

```bash
# Create the database
createdb ai_design_sandbox

# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend (in a separate terminal)
cd frontend
npm install
npm run dev
```

### Option C: One-command launcher

```bash
python run.py --all
```

## Architecture

```
Next.js Frontend (port 3000)  ←→  FastAPI Backend (port 8000)
                                       │
                           PostgreSQL 16 (port 5432)
```

Monorepo with two packages — `run.py` spawns subprocesses, Docker Compose for containerized workflow.

## Project Structure

```
ai_app/
├── backend/              # Python FastAPI server
│   ├── Dockerfile
│   ├── main.py
│   ├── app/
│   │   ├── config.py     # Pydantic Settings (env-driven)
│   │   ├── db/           # asyncpg pool + append-only migrations
│   │   ├── models/       # Pydantic v2 schemas
│   │   ├── routers/      # REST + WebSocket endpoints
│   │   └── services/     # Business logic (project, AI, streaming)
│   └── requirements.txt
├── frontend/             # Next.js 16 + React 19 + Tailwind CSS v4
│   ├── Dockerfile
│   ├── src/
│   │   └── app/
│   │       ├── components/   # Sidebar, ChatPanel, EditorPane, LiveCanvas, FileExplorer, MainContent
│   │       ├── hooks/        # useProjects, useChat, useFileSave
│   │       └── lib/          # API client, types, file icons
│   └── package.json
├── docs/                 # Documentation
├── docker-compose.yml    # 3-service Compose (backend, frontend, db)
├── run.py                # One-command launcher
└── .env                  # Environment variables (project root)
```

## Environment Variables

The `.env` file lives at the **project root** (`./.env`). Key variables:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string |
| `TARGET_URL` | AI provider API endpoint (OpenAI-compatible) |
| `JWT_TOKEN` | AI provider JWT bearer token |
| `MODEL` | AI model identifier |
| `FIGMA_CLIENT_ID` | Figma OAuth (Phase 3) |
| `FIGMA_CLIENT_SECRET` | Figma OAuth (Phase 3) |

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, asyncpg, httpx
- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS v4, Monaco Editor, react-markdown
- **Database:** PostgreSQL 16
- **Infrastructure:** Docker Compose

## Documentation

See the [docs](./docs/) directory for detailed architecture and setup guides. The project also maintains a [CLAUDE.md](./CLAUDE.md) with full implementation details, bug history, and coding conventions.
