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
from app.routers import ai, auth, chat, figma, projects, sandbox, upload  # noqa: E402
from app.services.ai_service import create_design_upload_provider, create_provider  # noqa: E402
from app.services.figma_service import FigmaService  # noqa: E402
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
    provider = None
    try:
        settings.validate_ai_config()
        provider = create_provider()
        ai.set_dependencies(provider, svc)
        app.state.ai_provider = provider
        print(f"  [AI] Provider configured: {settings.model}")
    except ValueError as e:
        print(f"  [AI] {e}")
        print(f"  [AI] AI generation endpoint will return 503 until configured.")

    # Initialise Figma service (stateless — no OAuth tokens)
    figma_svc = FigmaService()
    figma.set_dependencies(figma_svc, provider, svc)
    app.state.figma_service = figma_svc
    print(f"  [Figma] URL import available (requires personal access token)")

    # Initialise upload service
    upload.set_dependencies(provider, svc)
    # If a separate vision provider is configured, create a dedicated one for design upload
    if settings.design_upload_target_url or settings.design_upload_jwt_token or settings.design_upload_model:
        vision_provider = create_design_upload_provider()
        upload.set_vision_provider(vision_provider)
        print(f"  [Upload] Design upload using separate vision provider")
        if not settings.design_upload_target_url:
            print(f"    DESIGN_UPLOAD_TARGET_URL not set — falling back to TARGET_URL")
        if not settings.design_upload_jwt_token:
            print(f"    DESIGN_UPLOAD_JWT_TOKEN not set — falling back to JWT_TOKEN")
        if not settings.design_upload_model:
            print(f"    DESIGN_UPLOAD_MODEL not set — falling back to MODEL")
    else:
        print(f"  [Upload] Design upload available (max {settings.max_upload_size_mb} MB) (using main AI provider)")

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
app.include_router(figma.router)
app.include_router(upload.router)
app.include_router(auth.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
