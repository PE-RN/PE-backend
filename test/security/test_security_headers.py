"""
Phase 9 — CSP + Third-party Script Safety Tests
Gate: all tests in this file must pass before starting Phase 10.

Verifies:
- X-Frame-Options: DENY on all API responses (clickjacking prevention)
- Referrer-Policy header present and set correctly
- nginx.conf contains a Content-Security-Policy header directive
- nginx.conf contains frame-ancestors 'none' in its CSP
- index.html has no unpinned @latest CDN scripts
- index.html adds crossorigin attribute to CDN scripts
"""
import re
import pytest
from pathlib import Path

# Paths resolved relative to this test file's location
_REPO_ROOT = Path(__file__).parents[3]   # backend py/test/security/ → repo root
_NGINX_CONF = _REPO_ROOT / "frontend" / "nginx.conf"
_INDEX_HTML  = _REPO_ROOT / "frontend" / "index.html"


# ---------------------------------------------------------------------------
# FastAPI response headers (tested via async_client)
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_x_frame_options_deny(async_client):
    """Every API response must include X-Frame-Options: DENY."""
    response = await async_client.get("/this-route-does-not-exist-xyz")
    assert response.headers.get("x-frame-options") == "DENY", (
        f"X-Frame-Options missing or wrong: {dict(response.headers)}"
    )


@pytest.mark.anyio
async def test_referrer_policy(async_client):
    """Every API response must include Referrer-Policy."""
    response = await async_client.get("/this-route-does-not-exist-xyz")
    assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin", (
        f"Referrer-Policy missing or wrong: {dict(response.headers)}"
    )


@pytest.mark.anyio
async def test_x_content_type_options_still_present(async_client):
    """Regression: X-Content-Type-Options: nosniff must still be present (set in Phase 8)."""
    response = await async_client.get("/this-route-does-not-exist-xyz")
    assert response.headers.get("x-content-type-options") == "nosniff"


# ---------------------------------------------------------------------------
# nginx.conf — static analysis (file content checks)
# ---------------------------------------------------------------------------

def _nginx_text() -> str:
    assert _NGINX_CONF.exists(), f"nginx.conf not found at {_NGINX_CONF}"
    return _NGINX_CONF.read_text(encoding="utf-8")


def test_nginx_has_csp_header():
    """nginx.conf must declare a Content-Security-Policy header."""
    assert "Content-Security-Policy" in _nginx_text(), (
        "Content-Security-Policy directive missing from nginx.conf"
    )


def test_nginx_csp_has_frame_ancestors_none():
    """CSP in nginx.conf must include frame-ancestors 'none' (clickjacking prevention)."""
    assert "frame-ancestors 'none'" in _nginx_text(), (
        "frame-ancestors 'none' missing from CSP in nginx.conf"
    )


def test_nginx_csp_has_default_src_self():
    """CSP must restrict default-src to 'self'."""
    assert "default-src 'self'" in _nginx_text(), (
        "default-src 'self' missing from CSP in nginx.conf"
    )


def test_nginx_has_x_frame_options():
    """nginx.conf must set X-Frame-Options: DENY."""
    text = _nginx_text()
    assert 'X-Frame-Options' in text and 'DENY' in text, (
        "X-Frame-Options DENY missing from nginx.conf"
    )


def test_nginx_has_referrer_policy():
    """nginx.conf must set Referrer-Policy."""
    assert "Referrer-Policy" in _nginx_text(), (
        "Referrer-Policy missing from nginx.conf"
    )


# ---------------------------------------------------------------------------
# index.html — third-party script safety
# ---------------------------------------------------------------------------

def _html_text() -> str:
    assert _INDEX_HTML.exists(), f"index.html not found at {_INDEX_HTML}"
    return _INDEX_HTML.read_text(encoding="utf-8")


def test_no_unpinned_latest_scripts():
    """index.html must not load any CDN script tagged @latest or -latest."""
    html = _html_text()
    # Match src attributes containing @latest or -latest (e.g. plotly-latest, hls.js@latest)
    matches = re.findall(r'src=["\'][^"\']*(?:@latest|-latest)[^"\']*["\']', html)
    assert not matches, (
        f"Unpinned @latest / -latest scripts found in index.html:\n" +
        "\n".join(matches)
    )


def test_cdn_scripts_have_crossorigin():
    """External CDN <script> tags in index.html must include crossorigin attribute."""
    html = _html_text()
    # Find all <script> tags that load from external CDNs
    external_scripts = re.findall(
        r'<script[^>]+src=["\']https?://[^"\']+["\'][^>]*>', html
    )
    missing = [
        tag for tag in external_scripts
        if "crossorigin" not in tag
        # Google Analytics async scripts are intentionally excluded (dynamically injected)
        and "googletagmanager.com/gtag" not in tag
    ]
    assert not missing, (
        "External CDN script tags missing crossorigin attribute:\n" +
        "\n".join(missing)
    )
