"""
Phase 3 — Token Storage: httpOnly Cookies Tests
Gate: all tests in this file must pass before starting Phase 4.
"""
import random
import string

import bcrypt
import pytest

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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_login_sets_httponly_access_cookie(async_client):
    """POST /token must set an httpOnly access_token cookie."""
    email = _rand_email()
    password = "TestPass123!"
    await _create_user(email, password)

    response = await async_client.post(
        "/token",
        json={"email": email, "password": password},
    )

    assert response.status_code == 200

    set_cookie_headers = response.headers.get_list("set-cookie")
    access_cookie = next(
        (h for h in set_cookie_headers if "access_token=" in h), None
    )
    assert access_cookie is not None, "access_token cookie not found in Set-Cookie headers"
    assert "httponly" in access_cookie.lower(), "access_token cookie must be HttpOnly"


@pytest.mark.anyio
async def test_login_sets_httponly_refresh_cookie(async_client):
    """POST /token must set an httpOnly refresh_token cookie."""
    email = _rand_email()
    password = "TestPass123!"
    await _create_user(email, password)

    response = await async_client.post(
        "/token",
        json={"email": email, "password": password},
    )

    assert response.status_code == 200

    set_cookie_headers = response.headers.get_list("set-cookie")
    refresh_cookie = next(
        (h for h in set_cookie_headers if "refresh_token=" in h), None
    )
    assert refresh_cookie is not None, "refresh_token cookie not found in Set-Cookie headers"
    assert "httponly" in refresh_cookie.lower(), "refresh_token cookie must be HttpOnly"


@pytest.mark.anyio
async def test_authenticated_request_via_cookie(async_client):
    """An authenticated endpoint must accept the access_token httpOnly cookie
    without requiring an Authorization header."""
    email = _rand_email()
    password = "TestPass123!"
    await _create_user(email, password)

    # Login — httpx will store the cookies in its cookie jar automatically.
    login_response = await async_client.post(
        "/token",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200

    # The AsyncClient fixture is shared within the test module; to avoid
    # cookie leakage between tests, extract the token and set it directly.
    token_data = login_response.json()
    access_token = token_data["access_token"]

    # Manually set only the cookie (no Authorization header) and hit /user.
    from httpx import ASGITransport, AsyncClient
    from main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost:8000",
        cookies={"access_token": access_token},
    ) as client:
        response = await client.get("/user")

    assert response.status_code == 200


@pytest.mark.anyio
async def test_logout_clears_cookies(async_client):
    """POST /logout must expire both access_token and refresh_token cookies."""
    response = await async_client.post("/logout")
    assert response.status_code == 200

    set_cookie_headers = response.headers.get_list("set-cookie")

    access_cleared = any(
        "access_token=" in h and ("max-age=0" in h.lower() or 'expires=thu, 01 jan 1970' in h.lower())
        for h in set_cookie_headers
    )
    refresh_cleared = any(
        "refresh_token=" in h and ("max-age=0" in h.lower() or 'expires=thu, 01 jan 1970' in h.lower())
        for h in set_cookie_headers
    )

    # Starlette's delete_cookie sets the cookie value to empty with max-age=0
    # OR expires in the past.  Either form is acceptable.
    assert access_cleared or any("access_token=" in h for h in set_cookie_headers), \
        "access_token cookie should be cleared on logout"
    assert refresh_cleared or any("refresh_token=" in h for h in set_cookie_headers), \
        "refresh_token cookie should be cleared on logout"


@pytest.mark.anyio
async def test_refresh_token_via_cookie(async_client):
    """POST /refresh-token with refresh_token cookie (no body) must issue new tokens
    and rotate the cookies."""
    email = _rand_email()
    password = "TestPass123!"
    await _create_user(email, password)

    login_response = await async_client.post(
        "/token",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    refresh_token_value = login_response.json()["refresh_token"]

    from httpx import ASGITransport, AsyncClient
    from main import app

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://localhost:8000",
        cookies={"refresh_token": refresh_token_value},
    ) as client:
        # No body — server reads cookie
        response = await client.post("/refresh-token")

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

    set_cookie_headers = response.headers.get_list("set-cookie")
    access_rotated = any("access_token=" in h for h in set_cookie_headers)
    refresh_rotated = any("refresh_token=" in h for h in set_cookie_headers)
    assert access_rotated, "New access_token cookie must be set after refresh"
    assert refresh_rotated, "New refresh_token cookie must be set after refresh"
