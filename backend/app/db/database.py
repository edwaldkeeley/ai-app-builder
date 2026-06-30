"""PostgreSQL connection pool management and migration runner using asyncpg."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

# Retry settings for connection acquisition
_MAX_RETRIES = 3
_BASE_DELAY = 0.5  # seconds


async def init_pool(
    dsn: str,
    min_size: int = 2,
    max_size: int = 10,
) -> asyncpg.Pool:
    """Create and return a connection pool. Stores it internally."""
    global _pool
    if _pool is not None:
        return _pool
    _pool = await asyncpg.create_pool(
        dsn=dsn,
        min_size=min_size,
        max_size=max_size,
        command_timeout=30,
        timeout=10,  # seconds to wait for pool creation / initial connection
    )
    return _pool


async def close_pool() -> None:
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the active pool. Raises RuntimeError if not initialised."""
    if _pool is None:
        raise RuntimeError("Database pool not initialised. Call init_pool() first.")
    return _pool


async def acquire_with_retry(pool: asyncpg.Pool) -> asyncpg.Connection:
    """Acquire a connection from the pool with exponential backoff retry.

    Retries up to ``_MAX_RETRIES`` times with exponential backoff when the
    pool is exhausted or a connection cannot be established.
    Includes a health check (simple SELECT) to detect stale connections.
    """
    last_error: Exception | None = None
    delay = _BASE_DELAY

    for attempt in range(_MAX_RETRIES):
        try:
            conn = await pool.acquire(timeout=10)
            # Health check: verify connection is alive
            try:
                await conn.execute("SELECT 1")
            except (asyncpg.PostgresError, ConnectionError) as e:
                # Stale connection — release and retry
                await pool.release(conn)
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                    delay *= 2
                continue
            return conn
        except asyncpg.PoolAcquireError as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(delay)
                delay *= 2  # exponential backoff
        except asyncpg.PostgresError as e:
            # Non-retryable errors are re-raised immediately
            raise

    raise RuntimeError(
        f"Failed to acquire database connection after {_MAX_RETRIES} retries"
    ) from last_error


async def run_migrations(pool: asyncpg.Pool) -> None:
    """Execute all pending SQL migration files in order (append-only).

    Each migration runs inside a transaction along with its tracking insert
    into ``schema_migrations``, guaranteeing exactly-once execution.
    """
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))

    async with pool.acquire(timeout=10) as conn:
        # Bootstrap the tracking table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version     INTEGER PRIMARY KEY,
                filename    VARCHAR(255) NOT NULL,
                applied_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        applied = {row["version"] for row in await conn.fetch("SELECT version FROM schema_migrations")}

        for sql_file in sql_files:
            version = int(sql_file.stem.split("_")[0])

            if version in applied:
                logger.info("Skipping %s (already applied)", sql_file.name)
                continue

            sql = sql_file.read_text(encoding="utf-8")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, filename) VALUES ($1, $2)",
                    version,
                    sql_file.name,
                )
            logger.info("Applied %s", sql_file.name)
