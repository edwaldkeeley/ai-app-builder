"""FastAPI application entry point.

Run with::

    cd backend && uvicorn main:app --reload

or from the project root::

    python run.py
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure the backend package is importable when running from the project root
_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from app.config import settings  # noqa: E402
from app.db.database import close_pool, init_pool, run_migrations  # noqa: E402
from app.routers import ai, chat, projects, sandbox  # noqa: E402
from app.services.ai_service import create_provider  # noqa: E402
from app.services.project_service import ProjectService  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # ── Startup ────────────────────────────────────────────
    pool = await init_pool(
        dsn=settings.database_url,
        min_size=settings.database_pool_min_size,
        max_size=settings.database_pool_max_size,
    )
    await run_migrations(pool)

    svc = ProjectService()
    projects.set_project_service(svc)
    app.state.project_service = svc

    # Validate AI config (non-fatal — warns if not set)
    try:
        settings.validate_ai_config()
        provider = create_provider()
        ai.set_dependencies(provider, svc)
        app.state.ai_provider = provider
        print(f"  [AI] Provider configured: {settings.model}")
    except ValueError as e:
        print(f"  [AI] {e}")
        print(f"  [AI] AI generation endpoint will return 503 until configured.")

    print(f"  [START] {settings.app_name} running at http://{settings.host}:{settings.port}")
    print(f"  [DB] Connected to PostgreSQL")
    yield
    # ── Shutdown ───────────────────────────────────────────
    await close_pool()
    print("  [DB] Connection pool closed.")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS (allow Next.js dev server) ───────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────
app.include_router(projects.router)
app.include_router(sandbox.router)
app.include_router(ai.router)
app.include_router(chat.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
