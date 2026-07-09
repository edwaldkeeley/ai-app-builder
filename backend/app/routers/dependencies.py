"""Shared FastAPI dependencies — primarily auth."""

from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db.database import acquire_with_retry, get_pool
from app.services.auth_service import decode_access_token

security = HTTPBearer(auto_error=False)
COOKIE_KEY = "access_token"


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    """Extract and validate the current user from JWT (header or cookie).

    Returns a dict with id, email, username, created_at.
    Raises 401 if not authenticated.
    """
    token = None
    if credentials:
        token = credentials.credentials

    if not token:
        token = request.cookies.get(COOKIE_KEY)

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    pool = get_pool()
    conn = await acquire_with_retry(pool)
    try:
        row = await conn.fetchrow(
            "SELECT id, email, username, created_at FROM users WHERE id = $1",
            UUID(user_id),
        )
    finally:
        await pool.release(conn)

    if row is None:
        raise HTTPException(status_code=401, detail="User not found")

    return dict(row)
