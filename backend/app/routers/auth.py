"""Authentication endpoints: register, login, logout, me, settings."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.config import settings
from app.db.database import acquire_with_retry, get_pool
from app.models.schemas import ChangePasswordRequest, UpdateUserRequest
from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    change_password as svc_change_password,
    delete_user as svc_delete_user,
    update_user as svc_update_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── Schemas ────────────────────────────────────────────


class UserOut(BaseModel):
    id: UUID
    email: str
    username: str
    created_at: datetime
    updated_at: datetime | None = None


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=255)
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)


# ── Cookie helpers ─────────────────────────────────────

COOKIE_KEY = "access_token"


def _set_auth_cookie(response: Response, token: str) -> None:
    """Set the httpOnly JWT cookie on the response."""
    response.set_cookie(
        key=COOKIE_KEY,
        value=token,
        httponly=True,
        secure=not settings.debug,  # True in production (when DEBUG=False)
        samesite="lax",
        path="/",
        max_age=settings.access_token_expire_minutes * 60,
    )


def _clear_auth_cookie(response: Response) -> None:
    """Clear the httpOnly JWT cookie."""
    response.delete_cookie(key=COOKIE_KEY, path="/")


# ── Auth helpers ───────────────────────────────────────


async def get_current_user(request: Request) -> dict:
    """Extract and validate the current user from the request.

    Reads the JWT from the httpOnly cookie (or Authorization header).

    Returns the user row as a dict.

    Raises HTTPException(401) if not authenticated.
    """
    token = request.cookies.get(COOKIE_KEY)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

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
            "SELECT id, email, username, created_at, updated_at FROM users WHERE id = $1",
            UUID(user_id),
        )
    finally:
        await pool.release(conn)

    if row is None:
        raise HTTPException(status_code=401, detail="User not found")

    return dict(row)


# ── Endpoints ──────────────────────────────────────────


@router.post("/register", response_model=UserOut, status_code=201)
async def register(body: RegisterRequest, response: Response):
    """Register a new user account."""
    pool = get_pool()
    conn = await acquire_with_retry(pool)
    try:
        # Check for duplicate email
        existing = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1", body.email,
        )
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        password_hash = hash_password(body.password)
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, username, password_hash)
            VALUES ($1, $2, $3)
            RETURNING id, email, username, created_at, updated_at
            """,
            body.email,
            body.username,
            password_hash,
        )
    finally:
        await pool.release(conn)

    # Create JWT and set cookie
    token = create_access_token({"sub": str(row["id"])})
    _set_auth_cookie(response, token)

    return dict(row)


@router.post("/login", response_model=UserOut)
async def login(body: LoginRequest, response: Response):
    """Authenticate and log in a user."""
    pool = get_pool()
    conn = await acquire_with_retry(pool)
    try:
        row = await conn.fetchrow(
            "SELECT id, email, username, password_hash, created_at, updated_at FROM users WHERE email = $1",
            body.email,
        )
    finally:
        await pool.release(conn)

    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(row["id"])})
    _set_auth_cookie(response, token)

    return {
        "id": row["id"],
        "email": row["email"],
        "username": row["username"],
        "created_at": row["created_at"],
        "updated_at": row.get("updated_at"),
    }


@router.post("/logout")
async def logout(response: Response):
    """Log out by clearing the auth cookie."""
    _clear_auth_cookie(response)
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return current_user


@router.patch("/me", response_model=UserOut)
async def update_me(body: UpdateUserRequest, current_user: dict = Depends(get_current_user)):
    """Update the current user's profile (username, email)."""
    result = await svc_update_user(
        current_user["id"],
        username=body.username,
        email=body.email,
    )
    if result is None:
        # Check if it was a duplicate email vs not-found
        if body.email:
            pool = get_pool()
            conn = await acquire_with_retry(pool)
            try:
                existing = await conn.fetchval(
                    "SELECT id FROM users WHERE email = $1 AND id != $2",
                    body.email, current_user["id"],
                )
            finally:
                await pool.release(conn)
            if existing:
                raise HTTPException(status_code=409, detail="Email already in use")
        raise HTTPException(status_code=404, detail="User not found")
    return result


@router.post("/me/change-password")
async def change_my_password(body: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    """Change the current user's password."""
    success = await svc_change_password(
        current_user["id"],
        body.current_password,
        body.new_password,
    )
    if not success:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    return {"message": "Password changed successfully"}


@router.delete("/me", status_code=204)
async def delete_my_account(current_user: dict = Depends(get_current_user), response: Response = None):
    """Delete the current user's account and all associated data."""
    await svc_delete_user(current_user["id"])
    _clear_auth_cookie(response)
    return None
