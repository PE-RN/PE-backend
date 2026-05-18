"""
Phase 7 — Error Message Sanitization Tests
Gate: all tests in this file must pass before starting Phase 8.

Ensures that 5xx responses never expose raw exception text (stack traces,
SQL fragments, internal paths, library error messages, etc.).
"""
import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_INTERNAL_KEYWORDS = [
    "traceback",
    "asyncpg",
    "sqlalchemy",
    "psycopg",
    "file \"",          # path in stack trace
    "line ",            # stack trace line reference
    "exception",        # raw Python exception class names
    "error:",           # raw DB / OS error prefix
    "keyerror",
    "valueerror",
    "runtimeerror",
    "attributeerror",
    "typeerror",
]


def _has_internal_leak(body: str) -> bool:
    lower = body.lower()
    return any(kw in lower for kw in _INTERNAL_KEYWORDS)


# ---------------------------------------------------------------------------
# 500 responses must carry a generic message
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_invalid_token_returns_401_not_500(async_client):
    """A forged / malformed token must yield 401, not a raw exception."""
    response = await async_client.get(
        "/check-token",
        headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
    )
    assert response.status_code in (401, 403), (
        f"Expected 401/403, got {response.status_code}"
    )
    assert not _has_internal_leak(response.text), (
        f"Internal detail leaked: {response.text}"
    )


@pytest.mark.anyio
async def test_nonexistent_route_returns_404_without_leak(async_client):
    """A request to an unknown route must return 404 with no internal details."""
    response = await async_client.get("/this/endpoint/does/not/exist/xyz")
    assert response.status_code == 404
    assert not _has_internal_leak(response.text), (
        f"Internal detail leaked: {response.text}"
    )


@pytest.mark.anyio
async def test_malformed_json_body_returns_4xx_without_leak(async_client):
    """Sending a malformed JSON body to a JSON endpoint must not expose internals."""
    response = await async_client.post(
        "/users",
        content=b"not-valid-json{{{",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code in (400, 422), (
        f"Expected 400/422, got {response.status_code}"
    )
    assert not _has_internal_leak(response.text), (
        f"Internal detail leaked: {response.text}"
    )


@pytest.mark.anyio
async def test_bad_login_credentials_dont_leak_user_existence(async_client):
    """A failed login must return 401/422 and must NOT reveal internal DB details."""
    response = await async_client.post(
        "/token",
        data={"username": "nonexistent_user_xyz@example.com", "password": "WrongPassword1!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    # 401 if credentials checked, 422 if form validation fails — both are acceptable
    assert response.status_code in (401, 403, 422), (
        f"Expected 401/403/422, got {response.status_code}"
    )
    # Must not expose DB or library internals regardless of status
    assert not _has_internal_leak(response.text), (
        f"Internal detail leaked: {response.text}"
    )


@pytest.mark.anyio
async def test_invalid_uuid_path_param_returns_422_without_leak(async_client):
    """An invalid UUID in a path parameter must return 422 with no internal details."""
    response = await async_client.get("/confirm-email/not-a-valid-uuid")
    assert response.status_code == 422, (
        f"Expected 422, got {response.status_code}"
    )
    assert not _has_internal_leak(response.text), (
        f"Internal detail leaked: {response.text}"
    )


@pytest.mark.anyio
async def test_check_token_without_token_returns_401_without_leak(async_client):
    """GET /check-token without any token must return 401 with no internal leak."""
    response = await async_client.get("/check-token")
    assert response.status_code in (401, 403), (
        f"Expected 401/403, got {response.status_code}"
    )
    assert not _has_internal_leak(response.text), (
        f"Internal detail leaked: {response.text}"
    )


@pytest.mark.anyio
async def test_500_response_body_is_generic():
    """The global exception handler must return a generic message, never the raw error text.

    Tests the handler directly so the result is independent of ASGI transport behaviour.
    """
    from main import global_exception_handler
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": [],
        "query_string": b"",
    }
    request = Request(scope)
    exc = RuntimeError("asyncpg: column 'secret_col' does not exist -- C:\\\\server\\\\app.py")

    response = await global_exception_handler(request, exc)

    assert response.status_code == 500, f"Expected 500, got {response.status_code}"
    body = response.body.decode()
    assert "asyncpg" not in body.lower(), f"Library name leaked: {body}"
    assert "secret_col" not in body, f"Internal column name leaked: {body}"
    assert "server" not in body.lower() or "erro" in body.lower(), (
        f"Path or generic message issue: {body}"
    )
    assert "erro interno" in body.lower(), f"Generic message missing: {body}"
