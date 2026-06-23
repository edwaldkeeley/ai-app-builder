"""PostgreSQL connection pool management and migration runner using asyncpg."""

from __future__ import annotations

from pathlib import Path

import asyncpg

_pool: asyncpg.Pool | None = None


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


async def run_migrations(pool: asyncpg.Pool) -> None:
    """Execute all pending SQL migration files in order (append-only).

    Each migration runs inside a transaction along with its tracking insert
    into ``schema_migrations``, guaranteeing exactly-once execution.
    """
    migrations_dir = Path(__file__).resolve().parent / "migrations"
    sql_files = sorted(migrations_dir.glob("*.sql"))

    async with pool.acquire() as conn:
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
                print(f"  [MIGRATION] Skipping {sql_file.name} (already applied)")
                continue

            sql = sql_file.read_text(encoding="utf-8")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (version, filename) VALUES ($1, $2)",
                    version,
                    sql_file.name,
                )
            print(f"  [MIGRATION] Applied {sql_file.name}")
