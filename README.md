# AI Design Sandbox

An AI-powered design-to-code platform. Upload designs, describe what you want, or import from Figma — and get a full, editable web project with a live preview.

> **Status:** Phase 1 — Backend skeleton complete. Frontend coming next.

## Features (Roadmap)

- [x] **Backend API** — FastAPI with project CRUD and sandbox file management
- [ ] **Sandbox UI** — Monaco editor + live canvas + tab explorer
- [ ] **Design → HTML** — Upload an image and have AI convert it to code
- [ ] **Prompt → App** — Generate full frontend + backend from a text description
- [ ] **Figma Import** — OAuth flow to pull designs from Figma and convert to HTML
- [ ] **ZIP Export** — Download your project as a zip file
- [ ] **Pluggable AI** — Swap in your own model (Claude, GPT, local, etc.)

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

API docs: http://localhost:8000/docs

## Project Structure

```
ai_app/
├── backend/          # Python FastAPI server
│   ├── Dockerfile
│   ├── main.py
│   ├── app/
│   │   ├── config.py
│   │   ├── db/           # Database layer (asyncpg + migrations)
│   │   ├── models/       # Pydantic schemas
│   │   ├── routers/      # REST endpoints
│   │   └── services/     # Business logic
│   └── .env
├── frontend/         # Next.js React app (Phase 2)
│   ├── Dockerfile
│   └── ...
├── docs/             # Documentation
├── docker-compose.yml
├── run.py            # One-command launcher
└── README.md
```

## Documentation

See the [docs](./docs/) directory for detailed architecture and setup guides.
