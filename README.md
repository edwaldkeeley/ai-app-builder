# AI Design Sandbox

An AI-powered design-to-code platform. Describe what you want in natural language, and the platform generates a fully editable web project with a live preview and code editor.

> **Status:** Phase 3 complete — Figma URL import, ZIP export, design upload, multi-user auth, dark mode, 90 frontend tests, 169 backend tests.

## Features

- [x] **AI Code Generation** — Natural language → full HTML/CSS/JS projects with streaming WebSocket output
- [x] **Chat Interface** — ChatGPT-style conversation with markdown-rendered AI responses
- [x] **Monaco Editor** — Full-featured code editor with syntax highlighting, undo history, model-based tab switching
- [x] **Live Preview** — Sandboxed iframe that renders generated HTML/CSS/JS in real-time with viewport presets (Fluid/Desktop/Tablet/Mobile)
- [x] **File Explorer** — VS Code-style tree view with directory structure, file icons, rename/delete/new file
- [x] **View Modes** — Toggle between Preview, Code, and Split (50/50) layouts
- [x] **Chat Persistence** — Messages survive page refresh via PostgreSQL
- [x] **Auto-Save** — Debounced file saving to backend (800ms) with dirty file indicators
- [x] **WebSocket Streaming** — AI output streams character-by-character into chat and files in real-time
- [x] **Figma URL Import** — Paste a Figma URL + personal access token to generate code from designs
- [x] **Design Upload** — Upload a screenshot or mockup image and have AI convert it to code (two-stage vision pipeline)
- [x] **ZIP Export** — Download your project as a zip file
- [x] **Multi-User Auth** — Login/register system with JWT tokens and session management
- [x] **Dark Mode** — Light/dark theme toggle with system preference detection
- [x] **Toast Notifications** — Non-intrusive success/error/info notifications
- [x] **Keyboard Shortcuts** — Ctrl+S (save), Ctrl+B (toggle sidebar), Ctrl+Shift+E (toggle explorer), Escape (close overlays)
- [x] **Responsive Layout** — Mobile-friendly with overlay panels and hamburger menu
- [x] **Accessibility** — ARIA roles, focus management, reduced-motion support, screen reader announcements
- [x] **Frontend Tests** — 90 tests across API client, hooks, components, and utilities
- [x] **Backend Tests** — 169 tests across schemas, services, and API endpoints

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
│   │   └── services/     # Business logic (project, AI, streaming, auth, Figma)
│   ├── tests/            # 169 tests (pytest)
│   └── requirements.txt
├── frontend/             # Next.js 16 + React 19 + Tailwind CSS v4
│   ├── Dockerfile
│   ├── src/
│   │   └── app/
│   │       ├── components/   # Sidebar, ChatPanel, EditorPane, LiveCanvas, FileExplorer, MainContent, etc.
│   │       ├── hooks/        # useProjects, useChat, useFileSave, useKeyboardShortcuts
│   │       ├── contexts/     # AuthContext, ThemeContext
│   │       ├── lib/          # API client, types, file icons
│   │       └── __tests__/    # 90 frontend tests (Jest + RTL)
│   └── package.json
├── docs/                 # Documentation
├── docker-compose.yml    # 3-service Compose (backend, frontend, db)
├── run.py                # One-command launcher
└── .env                  # Environment variables (project root)
```

## Environment Variables

The `.env` file lives at the **project root** (`./.env`). Key variables:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `TARGET_URL` | Yes | AI provider API endpoint (OpenAI-compatible) |
| `JWT_TOKEN` | Yes | AI provider JWT bearer token |
| `MODEL` | Yes | AI model identifier |
| `DESIGN_UPLOAD_MODEL` | No | Separate vision model for design upload (defaults to MODEL) |
| `DESIGN_UPLOAD_TARGET_URL` | No | Vision model API endpoint (defaults to TARGET_URL) |
| `DESIGN_UPLOAD_JWT_TOKEN` | No | Vision model JWT token (defaults to JWT_TOKEN) |
| `MAX_TOKENS` | No | Maximum output tokens (default: 16384) |
| `TIMEOUT_SECONDS` | No | AI provider request timeout (default: 600) |

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Pydantic v2, asyncpg, httpx, bcrypt, python-jose
- **Frontend:** Next.js 16, React 19, TypeScript, Tailwind CSS v4, Monaco Editor, react-markdown
- **Database:** PostgreSQL 16
- **Testing:** pytest (backend), Jest + React Testing Library (frontend)
- **Infrastructure:** Docker Compose

## Running Tests

```bash
# Backend tests (169)
cd backend
pytest

# Frontend tests (90)
cd frontend
npm test
```

## Documentation

See the [docs](./docs/) directory for detailed architecture and setup guides. The project also maintains a [CLAUDE.md](./CLAUDE.md) with full implementation details, bug history, and coding conventions.
