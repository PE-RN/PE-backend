"""
Phase 10 — Debug Endpoint Removal Tests
Gate: all tests in this file must pass before the security review is closed.

Verifies:
- /sentry-debug returns 404 (endpoint removed)
- No registered route in the app matches /sentry-debug
- main.py source does not contain the trigger_error function
"""
import pytest
from pathlib import Path

_MAIN_PY = Path(__file__).parents[2] / "main.py"


# ---------------------------------------------------------------------------
# Runtime check — endpoint must not exist
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_sentry_debug_returns_404(async_client):
    """/sentry-debug must return 404, not 500 (division by zero) or 200."""
    response = await async_client.get("/sentry-debug")
    assert response.status_code == 404, (
        f"Expected 404 (removed endpoint), got {response.status_code}: {response.text}"
    )


# ---------------------------------------------------------------------------
# Route registry check — no route named trigger_error
# ---------------------------------------------------------------------------

def test_sentry_debug_not_in_routes():
    """The FastAPI app must have no route registered at /sentry-debug."""
    from main import app
    debug_routes = [
        r for r in app.routes
        if hasattr(r, "path") and r.path == "/sentry-debug"
    ]
    assert not debug_routes, (
        f"/sentry-debug is still registered as a route: {debug_routes}"
    )


# ---------------------------------------------------------------------------
# Static analysis — source must not contain the trigger function
# ---------------------------------------------------------------------------

def test_main_py_has_no_trigger_error():
    """main.py must not contain the trigger_error debug function."""
    source = _MAIN_PY.read_text(encoding="utf-8")
    assert "trigger_error" not in source, (
        "trigger_error function still present in main.py"
    )
    assert "/sentry-debug" not in source, (
        "/sentry-debug route definition still present in main.py"
    )
