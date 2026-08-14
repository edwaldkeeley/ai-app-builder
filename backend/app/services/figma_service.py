"""Figma API integration service.

Provides Figma REST API access with two-level caching:
- **L1**: In-memory dict for fast lookups within a session.
- **L2**: PostgreSQL (figma_cache table) for persistence across restarts.

The stateless ``FigmaService`` class handles rate-limited HTTP requests and
cache management. Data transformation (JSON filtering, tree walking, prompt
building) lives in ``figma_filter``, ``figma_tree_walker``, and ``figma_types``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

import httpx

from app.db.database import acquire_with_retry, get_pool
from app.services.figma_types import FigmaApiError, FigmaRateLimitError
from app.services.utils import parse_retry_after

logger = logging.getLogger(__name__)

FIGMA_API_URL = "https://api.figma.com/v1"

# Max retries for Figma API 429 responses
_FIGMA_MAX_RETRIES = 1  # only retry once — don't burn through rate limit

# In-memory L1 cache for Figma file responses
# Key: file_key, Value: (timestamp, response_data)
_figma_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_FIGMA_CACHE_TTL = 43200  # 12 hours

# Rate limiter: track last request time per token
_last_request_time: float = 0
_MIN_REQUEST_INTERVAL = 2.0  # minimum 2 seconds between requests


class FigmaService:
    """Handles Figma API interactions for design import.

    This is a stateless service — no OAuth tokens are stored. Authentication
    is done via personal access tokens passed directly to each API call.
    """

    # ── Figma API calls ───────────────────────────────────────

    async def _read_db_cache(self, file_key: str) -> dict[str, Any] | None:
        """Read Figma data from PostgreSQL cache if it exists and is not expired."""
        try:
            pool = get_pool()
            conn = await acquire_with_retry(pool)
            try:
                row = await conn.fetchrow(
                    "SELECT data FROM figma_cache "
                    "WHERE file_key = $1 "
                    "AND cached_at + (ttl_seconds * INTERVAL '1 second') > NOW()",
                    file_key,
                )
                if row:
                    logger.info("Figma DB cache HIT for file key: %s", file_key)
                    return json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
                return None
            finally:
                await pool.release(conn)
        except Exception as e:
            logger.warning("Figma DB cache read error for %s: %s", file_key, e)
            return None

    async def _write_db_cache(self, file_key: str, data: dict[str, Any], ttl: int = 43200) -> None:
        """Write Figma data to PostgreSQL cache."""
        try:
            pool = get_pool()
            conn = await acquire_with_retry(pool)
            try:
                data_json = json.dumps(data, ensure_ascii=False)
                await conn.execute(
                    "INSERT INTO figma_cache (file_key, data, cached_at, ttl_seconds) "
                    "VALUES ($1, $2::jsonb, NOW(), $3) "
                    "ON CONFLICT (file_key) DO UPDATE SET "
                    "  data = $2::jsonb, cached_at = NOW(), ttl_seconds = $3",
                    file_key, data_json, ttl,
                )
                size_mb = len(data_json) / 1024 / 1024
                logger.info("Figma DB cache WRITTEN for file key: %s (%.1f MB)", file_key, size_mb)
            finally:
                await pool.release(conn)
        except Exception as e:
            logger.warning("Figma DB cache write error for %s: %s", file_key, e)

    async def _delete_db_cache(self, file_key: str | None = None) -> int:
        """Delete Figma data from PostgreSQL cache.

        Args:
            file_key: If provided, only delete cache for this file key.
                      If None, delete all cache entries.

        Returns:
            Number of rows deleted.
        """
        try:
            pool = get_pool()
            conn = await acquire_with_retry(pool)
            try:
                if file_key:
                    result = await conn.execute(
                        "DELETE FROM figma_cache WHERE file_key = $1",
                        file_key,
                    )
                else:
                    result = await conn.execute("DELETE FROM figma_cache")
                # Extract count from asyncpg result string like "DELETE 5"
                count = int(result.split()[-1]) if result else 0
                logger.info("Figma DB cache DELETED %d entries (file_key=%s)", count, file_key or "ALL")
                return count
            finally:
                await pool.release(conn)
        except Exception as e:
            logger.warning("Figma DB cache delete error: %s", e)
            return 0

    async def request_with_retry(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> httpx.Response:
        """Make a Figma API request with caching, rate limiting, and 429 retry logic.

        Features:
        - **In-memory cache**: Repeated requests for the same file within 5 minutes
          return cached data instead of hitting the API.
        - **Rate limiting**: Enforces a minimum 2-second gap between requests to
          avoid hitting Figma's aggressive rate limits.
        - **Single retry**: Only retries once on 429 (retrying more just burns
          through the rate limit faster).
        - **Fails fast**: On 429, raises ``FigmaRateLimitError`` immediately
          with the retry-after duration.
        """
        global _last_request_time

        # ── Rate limiting: enforce minimum gap between requests ──
        now = time.time()
        since_last = now - _last_request_time
        if since_last < _MIN_REQUEST_INTERVAL and _last_request_time > 0:
            wait = _MIN_REQUEST_INTERVAL - since_last
            logger.debug("Rate limiter: waiting %.1fs before Figma API call", wait)
            await asyncio.sleep(wait)
        _last_request_time = time.time()

        # ── Check cache for GET requests ─────────────────────────
        is_file_request = "v1/files/" in url and method.upper() == "GET"
        if is_file_request:
            # Extract file key from URL
            file_key_match = re.search(r"/files/([^/?#]+)", url)
            if file_key_match:
                file_key = file_key_match.group(1)

                # 1. Check in-memory cache first (L1)
                cached = _figma_cache.get(file_key)
                if cached:
                    cache_time, cache_data = cached
                    if time.time() - cache_time < _FIGMA_CACHE_TTL:
                        logger.info("Figma memory cache HIT for file key: %s", file_key)
                        return httpx.Response(
                            status_code=200,
                            json=cache_data,
                            request=httpx.Request(method, url),
                        )

                # 2. Check PostgreSQL cache (L2 — persists across restarts)
                db_data = await self._read_db_cache(file_key)
                if db_data is not None:
                    # Populate in-memory cache too
                    _figma_cache[file_key] = (time.time(), db_data)
                    return httpx.Response(
                        status_code=200,
                        json=db_data,
                        request=httpx.Request(method, url),
                    )

                logger.info("Figma cache MISS for file key: %s", file_key)

        # ── Make the request ─────────────────────────────────────
        for attempt in range(_FIGMA_MAX_RETRIES + 1):
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method, url, headers=headers)

            if response.status_code == 429:
                wait = parse_retry_after(response)
                # Fail fast — don't retry, just tell the user to wait
                raise FigmaRateLimitError(
                    retry_after=wait,
                    message=f"Figma API rate limited (429). Retry after {wait}s. "
                    "Personal access tokens have strict rate limits. "
                    "Wait and try again, or use a different token.",
                )

            if not response.is_success:
                raise FigmaApiError(
                    status=response.status_code,
                    detail=f"Figma API returned {response.status_code}: {response.text[:500]}",
                )

            # ── Cache the response for GET file requests ─────────
            if is_file_request and file_key_match:
                file_key = file_key_match.group(1)
                try:
                    data = response.json()
                    _figma_cache[file_key] = (time.time(), data)
                    # Also persist to PostgreSQL so it survives restarts
                    await self._write_db_cache(file_key, data)
                    logger.info("Figma cache SET for file key: %s (%.1f MB)", file_key, len(json.dumps(data)) / 1024 / 1024)
                except Exception:
                    pass

            return response

        # Should not be reached
        raise FigmaRateLimitError(retry_after=60)

    @staticmethod
    async def clear_cache(file_key: str | None = None) -> int:
        """Clear the Figma file cache (memory + database).

        Args:
            file_key: If provided, only clear the cache for this specific file.
                      If None, clear the entire cache.

        Returns:
            Number of cache entries cleared.
        """
        global _figma_cache
        cleared = 0
        if file_key:
            # Clear memory
            if file_key in _figma_cache:
                del _figma_cache[file_key]
                cleared += 1
            # Clear database
            try:
                service = FigmaService()
                db_cleared = await service._delete_db_cache(file_key)
                cleared += db_cleared
            except Exception as e:
                logger.warning("Failed to clear DB cache for %s: %s", file_key, e)
            logger.info("Figma cache cleared for file key: %s (%d entries)", file_key, cleared)
            return cleared
        # Clear all
        count = len(_figma_cache)
        _figma_cache.clear()
        # Clear all database cache
        try:
            service = FigmaService()
            db_cleared = await service._delete_db_cache()
            cleared += db_cleared
        except Exception as e:
            logger.warning("Failed to clear all DB cache: %s", e)
        logger.info("Figma cache cleared entirely (%d memory + %d db)", count, cleared)
        return count + cleared

    @staticmethod
    def get_cache_info() -> dict[str, Any]:
        """Get cache statistics."""
        global _figma_cache
        return {
            "entries": len(_figma_cache),
            "keys": list(_figma_cache.keys()),
            "ttl_seconds": _FIGMA_CACHE_TTL,
        }
