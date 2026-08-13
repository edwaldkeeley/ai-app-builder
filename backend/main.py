"""FastAPI application entry point.

Run with::

    cd backend && uvicorn main:app --reload

or from the project root::

    python run.py
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# Ensure the backend package is importable when running from the project root
_backend_dir = Path(__file__).resolve().parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

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
        logger.info(f"  [AI] Provider configured: {settings.model}")
    except ValueError as e:
        logger.info(f"  [AI] {e}")
        logger.info(f"  [AI] AI generation endpoint will return 503 until configured.")

    # Initialise Figma service (stateless — no OAuth tokens)
    figma_svc = FigmaService()
    figma.set_dependencies(figma_svc, provider, svc)
    app.state.figma_service = figma_svc
    logger.info(f"  [Figma] URL import available (requires personal access token)")

    # Initialise upload service
    upload.set_dependencies(provider, svc)
    # If a separate vision provider is configured, create a dedicated one for design upload
    if settings.design_upload_target_url or settings.design_upload_jwt_token or settings.design_upload_model:
        vision_provider = create_design_upload_provider()
        upload.set_vision_provider(vision_provider)
        logger.info(f"  [Upload] Design upload using separate vision provider")
        if not settings.design_upload_target_url:
            logger.info(f"    DESIGN_UPLOAD_TARGET_URL not set — falling back to TARGET_URL")
        if not settings.design_upload_jwt_token:
            logger.info(f"    DESIGN_UPLOAD_JWT_TOKEN not set — falling back to JWT_TOKEN")
        if not settings.design_upload_model:
            logger.info(f"    DESIGN_UPLOAD_MODEL not set — falling back to MODEL")
    else:
        logger.info(f"  [Upload] Design upload available (max {settings.max_upload_size_mb} MB) (using main AI provider)")

    logger.info(f"  [START] {settings.app_name} running at http://{settings.host}:{settings.port}")
    logger.info(f"  [DB] Connected to PostgreSQL")
    yield
    # ── Shutdown ───────────────────────────────────────────
    await close_pool()
    logger.info("  [DB] Connection pool closed.")


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

# ── GZip compression for API responses ────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ── Global exception handlers ─────────────────────────────
# These ensure the API always returns structured JSON errors
# instead of raw HTML or opaque 500s.


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors — return 422 with field-level details."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Request validation failed",
            "errors": exc.errors(),
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle business-logic ValueErrors as 400 Bad Request."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for any unhandled exception — returns 500 JSON.

    Logs the full traceback for debugging but only returns a safe
    message to the client (no stack traces in production responses).
    """
    logger.exception("Unhandled exception on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
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
