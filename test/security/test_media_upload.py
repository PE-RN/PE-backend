"""
Phase 8 — Media Upload Hardening Tests
Gate: all tests in this file must pass before starting Phase 9.

Verifies:
- Blocked file-type extensions (executable, script, SVG, HTML…)
- MIME type / extension mismatch rejected
- File size limit enforced (> 20 MB → 413)
- Path-traversal attempts are sanitised
- X-Content-Type-Options: nosniff present on all responses
"""
import io
import pytest
from fastapi import HTTPException, status
from unittest.mock import AsyncMock

from controllers.media_controller import MediaController, _ALLOWED_EXTENSIONS, _MAX_UPLOAD_BYTES
from schemas.media import CreatePdf
from fastapi import UploadFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pdf_schema(**overrides) -> CreatePdf:
    defaults = {
        "path": "test_file",
        "category": "Relatório",
        "sub_category": "Eólica",
        "name": "Test File",
    }
    defaults.update(overrides)
    return CreatePdf(**defaults)


def _make_upload(filename: str, content: bytes = b"%PDF-1.4 test", content_type: str = "") -> UploadFile:
    if not content_type:
        # Pick from allowlist if possible, else leave blank
        from pathlib import Path as _Path
        ext = _Path(filename).suffix.lower()
        from controllers.media_controller import _ALLOWED_EXTENSIONS as _AE
        content_type = _AE.get(ext, "application/octet-stream")
    return UploadFile(filename=filename, file=io.BytesIO(content), headers={"content-type": content_type})


def _mock_controller() -> MediaController:
    """MediaController with a repository that never touches the DB."""
    mock_repo = AsyncMock()
    mock_repo.create_file = AsyncMock(return_value=None)
    return MediaController(repository=mock_repo)


# ---------------------------------------------------------------------------
# Extension allowlist
# ---------------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("bad_filename", [
    "malware.exe",
    "shell.sh",
    "script.js",
    "page.html",
    "image.svg",   # SVG can contain inline scripts
    "style.css",
    "payload.php",
    "backdoor.py",
    "archive.zip",
    "data.xml",
])
async def test_blocked_extension_raises_422(bad_filename: str, tmp_path, monkeypatch):
    """Disallowed extensions must be rejected with 422 before the file is written."""
    monkeypatch.chdir(tmp_path)

    controller = _mock_controller()
    upload = _make_upload(bad_filename)
    schema = _make_pdf_schema()

    with pytest.raises(HTTPException) as exc_info:
        await controller.create_file(schema, upload)

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "permitido" in exc_info.value.detail.lower(), (
        f"Expected 'permitido' in error detail, got: {exc_info.value.detail}"
    )


# ---------------------------------------------------------------------------
# MIME type / extension mismatch
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_mime_mismatch_raises_422(tmp_path, monkeypatch):
    """A file with .pdf extension but image/png content-type must be rejected."""
    monkeypatch.chdir(tmp_path)

    controller = _mock_controller()
    upload = UploadFile(
        filename="document.pdf",
        file=io.BytesIO(b"%PDF-1.4 fake"),
        headers={"content-type": "image/png"},   # wrong MIME for .pdf
    )
    schema = _make_pdf_schema()

    with pytest.raises(HTTPException) as exc_info:
        await controller.create_file(schema, upload)

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ---------------------------------------------------------------------------
# File size limit
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_oversized_file_raises_413(tmp_path, monkeypatch):
    """Files exceeding 20 MB must be rejected with 413."""
    monkeypatch.chdir(tmp_path)

    controller = _mock_controller()
    big_content = b"A" * (_MAX_UPLOAD_BYTES + 1)
    upload = _make_upload("document.pdf", content=big_content)
    schema = _make_pdf_schema()

    with pytest.raises(HTTPException) as exc_info:
        await controller.create_file(schema, upload)

    assert exc_info.value.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


@pytest.mark.anyio
async def test_file_at_size_limit_is_accepted(tmp_path, monkeypatch):
    """A file exactly at the 20 MB limit must be accepted."""
    monkeypatch.chdir(tmp_path)

    controller = _mock_controller()
    exact_content = b"A" * _MAX_UPLOAD_BYTES
    upload = _make_upload("document.pdf", content=exact_content)
    schema = _make_pdf_schema()

    # Should not raise; repository mock will return None
    await controller.create_file(schema, upload)
    controller.repository.create_file.assert_awaited_once()


# ---------------------------------------------------------------------------
# Path traversal prevention
# ---------------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("evil_path", [
    "../../../etc/passwd",
    "../../secret",
    "../sibling",
    "/absolute/path",
    "..\\..\\windows\\system32",
])
async def test_path_traversal_is_sanitised(evil_path: str, tmp_path, monkeypatch):
    """Files with traversal sequences in 'path' must be written inside assets/public only."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "assets" / "public").mkdir(parents=True)

    controller = _mock_controller()
    upload = _make_upload("document.pdf")
    schema = _make_pdf_schema(path=evil_path)

    # Must not raise; the path must be sanitised
    await controller.create_file(schema, upload)

    # Verify the file was written INSIDE assets/public, not outside tmp_path
    public_dir = tmp_path / "assets" / "public"
    written_files = list(public_dir.iterdir())
    assert len(written_files) == 1, f"Expected 1 file in assets/public, found: {written_files}"

    # No file should exist outside assets/public
    import os
    for root, dirs, files in os.walk(str(tmp_path)):
        if "assets" in root and "public" in root:
            continue
        assert not files, f"File written outside assets/public: {root}/{files}"


# ---------------------------------------------------------------------------
# Valid upload accepted
# ---------------------------------------------------------------------------

@pytest.mark.anyio
@pytest.mark.parametrize("filename,content_type", [
    ("report.pdf", "application/pdf"),
    ("photo.jpg",  "image/jpeg"),
    ("photo.jpeg", "image/jpeg"),
    ("chart.png",  "image/png"),
    ("video.mp4",  "video/mp4"),
])
async def test_valid_upload_is_accepted(filename: str, content_type: str, tmp_path, monkeypatch):
    """All allowed file types must be accepted without raising."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "assets" / "public").mkdir(parents=True)

    controller = _mock_controller()
    upload = UploadFile(
        filename=filename,
        file=io.BytesIO(b"valid content"),
        headers={"content-type": content_type},
    )
    schema = _make_pdf_schema()

    await controller.create_file(schema, upload)
    controller.repository.create_file.assert_awaited_once()


# ---------------------------------------------------------------------------
# X-Content-Type-Options header
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_x_content_type_options_nosniff(async_client):
    """Every response must include X-Content-Type-Options: nosniff."""
    response = await async_client.get("/this-route-does-not-exist-xyz")
    assert response.headers.get("x-content-type-options") == "nosniff", (
        f"X-Content-Type-Options header missing or wrong: {dict(response.headers)}"
    )
