"""
Phase 6 — Logout & Cache Cleanup Tests
Gate: all tests in this file must pass before starting Phase 7.
"""
import pytest


# ---------------------------------------------------------------------------
# Cache-Control: no-store header tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_login_endpoint_has_no_store(async_client):
    """POST /token must return Cache-Control: no-store to prevent credential caching."""
    response = await async_client.post(
        "/token",
        data={"username": "nonexistent@example.com", "password": "irrelevant"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # Even a 401/422 response must carry the no-store directive
    assert "no-store" in response.headers.get("cache-control", ""), (
        f"Cache-Control header missing 'no-store': {response.headers.get('cache-control')}"
    )


@pytest.mark.anyio
async def test_logout_endpoint_has_no_store(async_client):
    """POST /logout must return Cache-Control: no-store."""
    response = await async_client.post("/logout")
    assert "no-store" in response.headers.get("cache-control", ""), (
        f"Cache-Control header missing 'no-store': {response.headers.get('cache-control')}"
    )


@pytest.mark.anyio
async def test_check_token_endpoint_has_no_store(async_client):
    """GET /check-token must return Cache-Control: no-store."""
    response = await async_client.get("/check-token")
    assert "no-store" in response.headers.get("cache-control", ""), (
        f"Cache-Control header missing 'no-store': {response.headers.get('cache-control')}"
    )


@pytest.mark.anyio
async def test_refresh_token_endpoint_has_no_store(async_client):
    """POST /refresh-token must return Cache-Control: no-store."""
    response = await async_client.post("/refresh-token")
    assert "no-store" in response.headers.get("cache-control", ""), (
        f"Cache-Control header missing 'no-store': {response.headers.get('cache-control')}"
    )


@pytest.mark.anyio
async def test_users_endpoint_has_no_store(async_client):
    """GET /users must return Cache-Control: no-store (even unauthenticated)."""
    response = await async_client.get("/users")
    assert "no-store" in response.headers.get("cache-control", ""), (
        f"Cache-Control header missing 'no-store': {response.headers.get('cache-control')}"
    )


# ---------------------------------------------------------------------------
# POST /logout cookie-clearing tests (redundant safeguard — already in test_cookies.py)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_logout_returns_200(async_client):
    """POST /logout must always return 200 regardless of authentication state."""
    response = await async_client.post("/logout")
    assert response.status_code == 200


@pytest.mark.anyio
async def test_logout_clears_access_token_cookie(async_client):
    """POST /logout must instruct the browser to delete the access_token cookie."""
    response = await async_client.post("/logout")
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any("access_token=" in h for h in set_cookie_headers), (
        "access_token cookie directive missing from logout response"
    )


@pytest.mark.anyio
async def test_logout_clears_refresh_token_cookie(async_client):
    """POST /logout must instruct the browser to delete the refresh_token cookie."""
    response = await async_client.post("/logout")
    set_cookie_headers = response.headers.get_list("set-cookie")
    assert any("refresh_token=" in h for h in set_cookie_headers), (
        "refresh_token cookie directive missing from logout response"
    )
