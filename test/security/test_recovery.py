"""
Phase 1 – Password Recovery Security Tests
Gate: all tests in this file must pass before starting Phase 2.
"""
import hashlib
import random
import string
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import bcrypt
import pytest

from controllers.auth_controller import AuthController
from repositories.auth_repository import AuthRepository
from sql_app import models
from test.conftest import TesteSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_pw(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _rand_email() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase, k=8))
    return f"test_{suffix}@example.com"


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


# ---------------------------------------------------------------------------
# Route-level tests (black-box via HTTP client)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_recovery_unknown_email_returns_200(async_client):
    """Posting a non-existent email must return 200 (no user enumeration)."""
    response = await async_client.post(
        "/recovery-password",
        json={"user_email": "nobody_at_all@nowhere.invalid"},
    )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_recovery_known_email_returns_200(async_client):
    """Posting an existing email must also return 200."""
    email = _rand_email()
    await _create_user(email)

    with patch.object(AuthController, "_send_reset_link_email_wrapper"):
        response = await async_client.post(
            "/recovery-password",
            json={"user_email": email},
        )
    assert response.status_code == 200


@pytest.mark.anyio
async def test_recovery_does_not_reset_password_immediately(async_client):
    """After a recovery request the user's stored password must be unchanged."""
    email = _rand_email()
    original_hash = _hash_pw("OriginalPassword!")
    await _create_user(email, "OriginalPassword!")

    with patch.object(AuthController, "_send_reset_link_email_wrapper"):
        await async_client.post("/recovery-password", json={"user_email": email})

    async with TesteSessionLocal() as db:
        repo = AuthRepository(db)
        user = await repo.get_user_by_email(email)
        assert bcrypt.checkpw(b"OriginalPassword!", user.password.encode()), (
            "Password must not have been changed by the recovery request"
        )


@pytest.mark.anyio
async def test_recovery_token_stored_hashed(async_client):
    """The PasswordResetToken row must store the SHA-256 hash, not the raw token."""
    from sqlmodel import select
    email = _rand_email()
    await _create_user(email)

    captured_reset_link: list[str] = []

    def _capture_email(self, email_message):
        # Extract the reset link from the HTML to recover the raw token
        content = email_message.html_content
        import re
        match = re.search(r'href="([^"]+)"', content)
        if match:
            captured_reset_link.append(match.group(1))

    with patch.object(AuthController, "_send_reset_link_email_wrapper", _capture_email):
        await async_client.post("/recovery-password", json={"user_email": email})

    assert len(captured_reset_link) == 1, "Expected exactly one reset link to be captured"
    url = captured_reset_link[0]
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(url)
    raw_token = parse_qs(parsed.query).get("token", [None])[0]
    assert raw_token is not None

    expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    async with TesteSessionLocal() as db:
        result = await db.exec(
            select(models.PasswordResetToken).where(
                models.PasswordResetToken.token_hash == expected_hash
            )
        )
        token_row = result.first()

    assert token_row is not None, "PasswordResetToken row not found"
    assert token_row.token_hash == expected_hash, "Stored hash must equal sha256(raw_token)"
    assert token_row.token_hash != raw_token, "Raw token must NOT be stored in DB"


@pytest.mark.anyio
async def test_recovery_email_body_contains_no_plaintext_password(async_client):
    """The email sent during recovery must not contain any plaintext password."""
    import re
    email = _rand_email()
    await _create_user(email)

    captured_html: list[str] = []

    def _capture(self, email_message):
        captured_html.append(email_message.html_content)

    with patch.object(AuthController, "_send_reset_link_email_wrapper", _capture):
        await async_client.post("/recovery-password", json={"user_email": email})

    assert len(captured_html) == 1
    html = captured_html[0]
    # A 9-digit all-numeric string is the old temporary password pattern
    assert not re.search(r"\b\d{9}\b", html), (
        "Email body must not contain a 9-digit temporary password"
    )
    # Email body should not contain the word "senha" next to a numeric sequence
    assert "nova_senha" not in html.lower()


# ---------------------------------------------------------------------------
# Reset-password endpoint tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_reset_password_valid_token(async_client):
    """A valid, unused, non-expired token must update the user's password."""
    email = _rand_email()
    user = await _create_user(email, "OldPassword1!")

    raw_token = "validtoken_" + uuid4().hex
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    async with TesteSessionLocal() as db:
        repo = AuthRepository(db)
        await repo.create_password_reset_token(user.id, token_hash, expires_at)

    response = await async_client.post(
        "/reset-password",
        json={"token": raw_token, "new_password": "NewPassword1!"},
    )
    assert response.status_code == 200

    async with TesteSessionLocal() as db:
        repo = AuthRepository(db)
        updated_user = await repo.get_user_by_email(email)
        assert bcrypt.checkpw(b"NewPassword1!", updated_user.password.encode()), (
            "Password must have been updated to the new value"
        )


@pytest.mark.anyio
async def test_reset_password_expired_token(async_client):
    """An expired token must be rejected with 400."""
    email = _rand_email()
    user = await _create_user(email)

    raw_token = "expiredtoken_" + uuid4().hex
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)  # already expired

    async with TesteSessionLocal() as db:
        repo = AuthRepository(db)
        await repo.create_password_reset_token(user.id, token_hash, expires_at)

    response = await async_client.post(
        "/reset-password",
        json={"token": raw_token, "new_password": "NewPassword1!"},
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_reset_password_used_token(async_client):
    """A token that has already been used must be rejected with 400."""
    email = _rand_email()
    user = await _create_user(email)

    raw_token = "usedtoken_" + uuid4().hex
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    async with TesteSessionLocal() as db:
        repo = AuthRepository(db)
        token_row = await repo.create_password_reset_token(user.id, token_hash, expires_at)
        await repo.mark_password_reset_token_used(token_row)

    response = await async_client.post(
        "/reset-password",
        json={"token": raw_token, "new_password": "NewPassword1!"},
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_reset_password_invalid_token(async_client):
    """A completely random/unknown token must be rejected with 400."""
    response = await async_client.post(
        "/reset-password",
        json={"token": "this_is_not_a_real_token_" + uuid4().hex, "new_password": "Anything1!"},
    )
    assert response.status_code == 400


@pytest.mark.anyio
async def test_old_recovery_route_gone(async_client):
    """The old GET /recovery-password/{email} route must no longer exist."""
    response = await async_client.get("/recovery-password/test@example.com")
    assert response.status_code in (404, 405), (
        f"Old GET route must be gone, got {response.status_code}"
    )
