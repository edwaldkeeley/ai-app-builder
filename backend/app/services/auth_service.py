"""Authentication service: password hashing, JWT creation/validation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.db.database import acquire_with_retry, get_pool

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    return _pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token.

    Args:
        data: Claims to include in the token (must include 'sub').
        expires_delta: Optional custom expiration. Defaults to settings value.

    Raises:
        RuntimeError: If ``secret_key`` is not configured.
    """
    if not settings.secret_key:
        raise RuntimeError(
            "SECRET_KEY is not configured. Set it in your .env file or environment."
        )
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict | None:
    """Decode and validate a JWT access token.

    Returns the payload dict on success, or None if the token is invalid/expired.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


async def update_user(user_id: UUID, username: str | None = None, email: str | None = None) -> dict | None:
    """Update user profile fields.

    Args:
        user_id: The user's UUID.
        username: New username (or None to skip).
        email: New email (or None to skip).

    Returns:
        Updated user dict, or None if user not found.
    """
    if username is None and email is None:
        return await get_user(user_id)

    sets = []
    params: list = []
    idx = 1

    if username is not None:
        sets.append(f"username = ${idx}")
        params.append(username)
        idx += 1
    if email is not None:
        sets.append(f"email = ${idx}")
        params.append(email)
        idx += 1

    sets.append(f"updated_at = NOW()")
    params.append(user_id)

    pool = get_pool()
    conn = await acquire_with_retry(pool)
    try:
        # Check email uniqueness if changing
        if email is not None:
            existing = await conn.fetchval(
                "SELECT id FROM users WHERE email = $1 AND id != $2",
                email, user_id,
            )
            if existing:
                return None  # Signal duplicate email

        row = await conn.fetchrow(
            f"UPDATE users SET {', '.join(sets)} WHERE id = ${idx} "
            "RETURNING id, email, username, created_at, updated_at",
            *params,
        )
    finally:
        await pool.release(conn)

    return dict(row) if row else None


async def change_password(user_id: UUID, current_password: str, new_password: str) -> bool:
    """Change a user's password.

    Args:
        user_id: The user's UUID.
        current_password: The current password for verification.
        new_password: The new password to set.

    Returns:
        True if password was changed, False if current password is wrong.
    """
    pool = get_pool()
    conn = await acquire_with_retry(pool)
    try:
        row = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1",
            user_id,
        )
        if row is None or not verify_password(current_password, row["password_hash"]):
            return False

        new_hash = hash_password(new_password)
        await conn.execute(
            "UPDATE users SET password_hash = $1, updated_at = NOW() WHERE id = $2",
            new_hash, user_id,
        )
        return True
    finally:
        await pool.release(conn)


async def delete_user(user_id: UUID) -> bool:
    """Delete a user account and all associated data (cascades to projects).

    Args:
        user_id: The user's UUID.

    Returns:
        True if deleted, False if not found.
    """
    pool = get_pool()
    conn = await acquire_with_retry(pool)
    try:
        result = await conn.execute("DELETE FROM users WHERE id = $1", user_id)
        return "DELETE 1" in result
    finally:
        await pool.release(conn)


async def get_user(user_id: UUID) -> dict | None:
    """Get a user by ID.

    Args:
        user_id: The user's UUID.

    Returns:
        User dict or None if not found.
    """
    pool = get_pool()
    conn = await acquire_with_retry(pool)
    try:
        row = await conn.fetchrow(
            "SELECT id, email, username, created_at, updated_at FROM users WHERE id = $1",
            user_id,
        )
        return dict(row) if row else None
    finally:
        await pool.release(conn)
