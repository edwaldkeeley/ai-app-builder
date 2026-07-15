"""Shared utility functions for the backend services."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx


def parse_retry_after(response: httpx.Response, default: int = 10) -> int:
    """Parse the Retry-After header from a 429 response.

    Handles both integer seconds (``Retry-After: 120``) and HTTP-date
    (``Retry-After: Fri, 31 Dec 2021 23:59:59 GMT``) formats per RFC 7231.

    Falls back to the response body's ``retry_after`` / ``Retry-After`` fields,
    then to the provided ``default``.
    Capped at 120 seconds to avoid bogus values.
    """
    header = response.headers.get("Retry-After")
    if header:
        try:
            return min(int(header), 120)
        except ValueError:
            pass
        try:
            parsed = datetime.strptime(header, "%a, %d %b %Y %H:%M:%S %Z")
            now = datetime.now(timezone.utc)
            wait = (parsed.replace(tzinfo=timezone.utc) - now).total_seconds()
            if wait > 0:
                return min(int(wait), 120)
        except ValueError:
            pass
    try:
        body = response.json()
        val = body.get("retry_after", body.get("Retry-After", default))
        return min(int(val), 120)
    except Exception:
        return default
