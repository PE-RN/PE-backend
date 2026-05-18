"""
Phase 2 — JWT Token Type Enforcement Tests
Gate: all tests in this file must pass before starting Phase 3.
"""
import hashlib
import random
import string
from datetime import datetime, timedelta, timezone
from os import getenv
from uuid import uuid4

import bcrypt
import pytest
from jose import jwt

from controllers.auth_controller import AuthController
from repositories.auth_repository import AuthRepository
from sql_app import models
from test.conftest import TesteSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rand_email() -> str:
    return f"test_{''.join(random.choices(string.ascii_lowercase, k=8))}@example.com"


def _hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def _create_user(email: str, password: str = "TestPass123!") -> models.User:
    async with TesteSessionLocal() as db:
        repo = AuthRepository(db)
        user = models.User(
            email=email,
            password=_hash_pw(password),
            ocupation="pesquisador",
            gender="M",
            education="graduacao",
            institution="UFRN",
            age="25",
            user="Test User",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


def _decode_token(token: str) -> dict:
    """Decode without verifying (we just need to inspect claims)."""
    return jwt.decode(
        token,
        getenv("SECRET_KEY"),
        algorithms=[getenv("ALGORITHM")],
        options={"verify_exp": False},
    )


# ---------------------------------------------------------------------------
# Token payload tests (unit-level)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_access_token_contains_typ_access(async_client):
    """Access tokens must carry typ=access."""
    email = _rand_email()
    await _create_user(email, "SomePass1!")

    response = await async_client.post(
        "/token",
        json={"email": email, "password": "SomePass1!"},
    )
    assert response.status_code == 200
    access_token = response.json()["access_token"]
    payload = _decode_token(access_token)
    assert payload.get("typ") == "access", f"Expected typ='access', got: {payload.get('typ')}"


@pytest.mark.anyio
async def test_refresh_token_contains_typ_refresh(async_client):
    """Refresh tokens must carry typ=refresh."""
    email = _rand_email()
    await _create_user(email, "SomePass1!")

    response = await async_client.post(
        "/token",
        json={"email": email, "password": "SomePass1!"},
    )
    assert response.status_code == 200
    refresh_token = response.json()["refresh_token"]
    payload = _decode_token(refresh_token)
    assert payload.get("typ") == "refresh", f"Expected typ='refresh', got: {payload.get('typ')}"


# ---------------------------------------------------------------------------
# Refresh endpoint enforcement tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_refresh_endpoint_rejects_access_token(async_client):
    """POST /refresh must reject a token with typ=access → 401."""
    email = _rand_email()
    await _create_user(email, "SomePass1!")

    login = await async_client.post(
        "/token",
        json={"email": email, "password": "SomePass1!"},
    )
    access_token = login.json()["access_token"]

    response = await async_client.post("/refresh-token", json={"refresh_token": access_token})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_refresh_endpoint_accepts_refresh_token(async_client):
    """POST /refresh must accept a valid refresh token → 200, returns new token pair."""
    email = _rand_email()
    await _create_user(email, "SomePass1!")

    login = await async_client.post(
        "/token",
        json={"email": email, "password": "SomePass1!"},
    )
    refresh_token = login.json()["refresh_token"]

    response = await async_client.post("/refresh-token", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


# ---------------------------------------------------------------------------
# Password change invalidates refresh token
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_password_change_invalidates_refresh_token(async_client):
    """After changing password, the pre-change refresh token must be rejected → 401."""
    email = _rand_email()
    await _create_user(email, "OldPass1!")

    # Login and capture refresh token
    login = await async_client.post(
        "/token",
        json={"email": email, "password": "OldPass1!"},
    )
    assert login.status_code == 200
    old_refresh_token = login.json()["refresh_token"]
    old_access_token = login.json()["access_token"]

    # Change password
    change = await async_client.post(
        "/change-password",
        json={"password": "OldPass1!", "new_password": "NewPass1!"},
        headers={"Authorization": f"Bearer {old_access_token}"},
    )
    assert change.status_code == 200

    # Old refresh token must now be invalid
    response = await async_client.post("/refresh-token", json={"refresh_token": old_refresh_token})
    assert response.status_code == 401, (
        "Refresh token issued before password change must be rejected after password change"
    )


@pytest.mark.anyio
async def test_reset_password_invalidates_refresh_token(async_client):
    """After password reset via link, the pre-reset refresh token must be rejected → 401."""
    from unittest.mock import patch
    email = _rand_email()
    user = await _create_user(email, "OldPass1!")

    # Login and capture refresh token
    login = await async_client.post(
        "/token",
        json={"email": email, "password": "OldPass1!"},
    )
    assert login.status_code == 200
    old_refresh_token = login.json()["refresh_token"]

    # Manually insert a valid reset token
    raw_token = "resettoken_" + uuid4().hex
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    async with TesteSessionLocal() as db:
        repo = AuthRepository(db)
        await repo.create_password_reset_token(user.id, token_hash, expires_at)

    # Execute reset
    reset = await async_client.post(
        "/reset-password",
        json={"token": raw_token, "new_password": "NewPass1!"},
    )
    assert reset.status_code == 200

    # Old refresh token must now be invalid
    response = await async_client.post("/refresh-token", json={"refresh_token": old_refresh_token})
    assert response.status_code == 401, (
        "Refresh token issued before password reset must be rejected after reset"
    )

