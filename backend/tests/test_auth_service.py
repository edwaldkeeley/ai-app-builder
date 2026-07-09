"""Tests for auth service: password hashing, JWT creation/validation."""

from __future__ import annotations

from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "testpassword123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_verify_wrong_password(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)

    def test_hash_is_different_each_time(self):
        pwd = "samepassword"
        h1 = hash_password(pwd)
        h2 = hash_password(pwd)
        assert h1 != h2  # bcrypt uses different salts


class TestJWT:
    def test_create_and_decode(self):
        token = create_access_token({"sub": "user-id-123"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-id-123"

    def test_decode_invalid_token(self):
        payload = decode_access_token("invalid-token")
        assert payload is None

    def test_decode_expired_token(self):
        from datetime import timedelta

        token = create_access_token({"sub": "test"}, expires_delta=timedelta(seconds=-1))
        payload = decode_access_token(token)
        assert payload is None
