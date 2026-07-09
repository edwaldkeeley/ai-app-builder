"""Test configuration, fixtures, and shared utilities.

Unit tests (schemas, ai_service, figma_service) don't need a database.
Integration tests (API endpoints) use a test database.

All tests use a mock AI provider to avoid hitting the real API.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any, AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure we're using test settings before importing app modules
_DB_HOST = os.environ.get("TEST_DB_HOST", "localhost")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", f"postgresql://postgres:postgres@{_DB_HOST}:5432/ai_design_sandbox_test")
os.environ.setdefault("DATABASE_POOL_MIN_SIZE", "1")
os.environ.setdefault("DATABASE_POOL_MAX_SIZE", "2")
os.environ.setdefault("TARGET_URL", "http://test-ai.local/v1/chat/completions")
os.environ.setdefault("JWT_TOKEN", "test-jwt-token")
os.environ.setdefault("MODEL", "test-model")

from app.models.schemas import FileType, ProjectFile  # noqa: E402
from app.services.ai_service import BaseAIProvider  # noqa: E402
from app.services.figma_service import FigmaService  # noqa: E402


# ── Mock AI provider ──────────────────────────────────────────


class MockAIProvider(BaseAIProvider):
    """Mock AI provider that returns predictable responses.

    Avoids hitting the real AI provider during tests.
    """

    def __init__(self) -> None:
        self.generate_calls: list[dict[str, Any]] = []
        self.default_message = "Test response from mock AI."
        self.default_files = [
            ProjectFile(path="index.html", content="<html><body>Test</body></html>", file_type=FileType.html),
            ProjectFile(path="style.css", content="body { color: red; }", file_type=FileType.css),
            ProjectFile(path="script.js", content="// test", file_type=FileType.js),
        ]

    async def generate(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
    ) -> tuple[str, list[ProjectFile]]:
        self.generate_calls.append({
            "prompt": prompt,
            "existing_files": existing_files,
            "chat_history": chat_history,
            "system_prompt_override": system_prompt_override,
        })
        return self.default_message, self.default_files

    async def generate_stream(
        self,
        prompt: str,
        existing_files: list[ProjectFile] | None = None,
        chat_history: list[dict[str, str]] | None = None,
        system_prompt_override: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "message_chunk", "delta": "Test "}
        yield {"type": "message_chunk", "delta": "response"}
        for f in self.default_files:
            yield {"type": "file_start", "path": f.path, "file_type": f.file_type.value}
            yield {"type": "file_chunk", "path": f.path, "delta": f.content}
            yield {"type": "file_done", "path": f.path}
        yield {
            "type": "done",
            "message": self.default_message,
            "files": [f.model_dump() for f in self.default_files],
        }


# ── Shared fixtures ───────────────────────────────────────────


@pytest.fixture
def mock_ai_provider() -> MockAIProvider:
    """Create a mock AI provider for testing."""
    return MockAIProvider()


@pytest.fixture
def figma_service() -> FigmaService:
    """Create a FigmaService instance."""
    return FigmaService()


# ── Integration test fixtures (require DB) ────────────────────


@pytest_asyncio.fixture
def event_loop():
    """Create a new event loop for each test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_pool():
    """Create the test database and connection pool."""
    import asyncpg

    # Create test database if it doesn't exist
    try:
        admin_conn = await asyncpg.connect(
            user="postgres", password="postgres",
            host=_DB_HOST, port=5432,
            database="postgres",
        )
        exists = await admin_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'ai_design_sandbox_test'"
        )
        if not exists:
            await admin_conn.execute("CREATE DATABASE ai_design_sandbox_test")
        await admin_conn.close()
    except Exception as e:
        pytest.skip(f"Cannot create test database: {e}")
        return

    from app.db.database import init_pool, run_migrations
    pool = await init_pool(
        f"postgresql://postgres:postgres@{_DB_HOST}:5432/ai_design_sandbox_test",
        min_size=1, max_size=2,
    )
    await run_migrations(pool)
    yield pool

    # Cleanup
    await pool.close()
    # Reset the global pool so next test session re-initializes
    from app.db import database as db_module
    db_module._pool = None
    try:
        admin_conn = await asyncpg.connect(
            user="postgres", password="postgres",
            host=_DB_HOST, port=5432,
            database="postgres",
        )
        await admin_conn.execute(
            "SELECT pg_terminate_backend(pg_stat_activity.pid) "
            "FROM pg_stat_activity "
            "WHERE pg_stat_activity.datname = 'ai_design_sandbox_test' "
            "AND pid <> pg_backend_pid()"
        )
        await admin_conn.execute("DROP DATABASE IF EXISTS ai_design_sandbox_test")
        await admin_conn.close()
    except Exception:
        pass


@pytest_asyncio.fixture
async def project_service(db_pool):
    """Create a ProjectService (uses the global pool set by db_pool)."""
    # db_pool is requested to ensure the pool is initialized
    from app.services.project_service import ProjectService
    return ProjectService()


@pytest_asyncio.fixture
async def test_app(db_pool, mock_ai_provider):
    """Create the FastAPI app with mocked dependencies for testing."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from app.config import settings
    from app.routers import ai, auth, chat, figma, projects, sandbox

    app = FastAPI(title="AI Design Sandbox Test")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(projects.router)
    app.include_router(sandbox.router)
    app.include_router(ai.router)
    app.include_router(chat.router)
    app.include_router(figma.router)
    app.include_router(auth.router)

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "app": settings.app_name}

    # Wire up dependencies
    from app.services.project_service import ProjectService
    svc = ProjectService()
    projects.set_project_service(svc)
    app.state.project_service = svc

    ai.set_dependencies(mock_ai_provider, svc)
    app.state.ai_provider = mock_ai_provider

    figma_svc = FigmaService()
    figma.set_dependencies(figma_svc, mock_ai_provider, svc)
    app.state.figma_service = figma_svc

    return app


@pytest_asyncio.fixture
async def async_client(test_app) -> AsyncIterator[AsyncClient]:
    """Create an async HTTP client for testing endpoints."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def sample_project(project_service, test_user):
    """Create a sample project for testing."""
    from app.models.schemas import ProjectCreate
    user, _ = test_user
    project = await project_service.create(
        ProjectCreate(name="Test Project", description="A test project"),
        user_id=user["id"],
    )
    return project


@pytest_asyncio.fixture
async def project_with_files(project_service, sample_project):
    """Create a sample project with some files."""
    files = [
        ProjectFile(path="index.html", content="<html><body>Hello</body></html>", file_type=FileType.html),
        ProjectFile(path="style.css", content="body { color: blue; }", file_type=FileType.css),
        ProjectFile(path="script.js", content="console.log('test');", file_type=FileType.js),
    ]
    await project_service.upsert_files_transactional(sample_project.id, files)
    return await project_service.get(sample_project.id)


# ── Auth fixtures ─────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_user(db_pool):
    """Create a test user and return user data + auth token."""
    from app.services.auth_service import create_access_token, hash_password
    from app.db.database import acquire_with_retry, get_pool

    pool = get_pool()
    conn = await acquire_with_retry(pool)
    try:
        row = await conn.fetchrow(
            "INSERT INTO users (email, username, password_hash) "
            "VALUES ($1, $2, $3) "
            "RETURNING id, email, username, created_at",
            "test@example.com",
            "testuser",
            hash_password("testpass123"),
        )
    finally:
        await pool.release(conn)
    token = create_access_token({"sub": str(row["id"])})
    return dict(row), token


@pytest_asyncio.fixture
async def auth_client(test_app, test_user):
    """Async client with auth cookie pre-set."""
    user, token = test_user
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.cookies.set("access_token", token)
        yield client
