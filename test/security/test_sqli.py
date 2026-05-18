"""
Phase 4 — SQL Injection in Geo Queries Tests
Gate: all tests in this file must pass before starting Phase 5.

Strategy:
  - Unit-test normalize_table_name directly (no DB required).
  - Integration-test the raster route: malformed table names and non-integer
    tile coordinates must be rejected before any DB query is attempted.
"""
import pytest

from repositories.geo_repository import GeoRepository
from main import app

# ---------------------------------------------------------------------------
# Unit tests — normalize_table_name
# ---------------------------------------------------------------------------

SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE users; --",
    "users UNION SELECT * FROM users",
    "raster; TRUNCATE TABLE raster",
    "1; SELECT pg_sleep(5)--",
    "raster\x00injected",
    "../../etc/passwd",
    "raster' OR '1'='1",
]

VALID_TABLE_NAMES = [
    ("wind_data", "wind_data"),
    ("Solar", "solar"),
    ("Wind-Speed", "wind_speed"),
    ("raster data", "raster_data"),
    ("GHI_2023", "ghi_2023"),
    ("_private", "_private"),
]


@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_normalize_table_name_rejects_sql_injection(payload: str):
    """normalize_table_name must raise ValueError for SQL injection payloads."""
    with pytest.raises(ValueError):
        GeoRepository.normalize_table_name(payload)


@pytest.mark.parametrize("input_name, expected", VALID_TABLE_NAMES)
def test_normalize_table_name_accepts_valid_names(input_name: str, expected: str):
    """normalize_table_name must accept and canonicalize valid table names."""
    assert GeoRepository.normalize_table_name(input_name) == expected


# ---------------------------------------------------------------------------
# Unit tests — repository methods reject malicious input before touching DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
async def test_get_raster_raises_value_error_for_sqli(payload: str):
    """get_raster must raise ValueError before executing any SQL."""
    from unittest.mock import MagicMock
    repo = GeoRepository(db=MagicMock())
    with pytest.raises(ValueError):
        await repo.get_raster(payload, 1, 1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
async def test_get_raster_dataset_raises_value_error_for_sqli(payload: str):
    """get_raster_dataset must raise ValueError before executing any SQL."""
    from unittest.mock import MagicMock
    repo = GeoRepository(db=MagicMock())
    with pytest.raises(ValueError):
        await repo.get_raster_dataset(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
async def test_get_polygon_by_name_raises_value_error_for_sqli(payload: str):
    """get_polygon_by_name must raise ValueError before executing any SQL."""
    from unittest.mock import MagicMock
    repo = GeoRepository(db=MagicMock())
    with pytest.raises(ValueError):
        await repo.get_polygon_by_name(payload)


@pytest.mark.asyncio
async def test_get_raster_rejects_non_integer_tile_coordinates():
    """get_raster must raise ValueError when tile coordinates cannot be cast to int."""
    from unittest.mock import MagicMock
    repo = GeoRepository(db=MagicMock())
    with pytest.raises((ValueError, TypeError)):
        await repo.get_raster("valid_table", "abc", "xyz", "not_an_int")


# ---------------------------------------------------------------------------
# Route schema tests — tile coordinates must be typed as int
# ---------------------------------------------------------------------------

def test_raster_route_declares_integer_tile_coordinates():
    """
    The raster route must declare x, y, z as int so FastAPI returns 422
    for non-integer path segments before any SQL is executed.
    """
    route = next(
        r for r in app.routes
        if getattr(r, "path", None) == "/geofiles/raster/{z}/{x}/{y}/{table_name}"
    )
    annotations = route.endpoint.__annotations__
    assert annotations.get("x") is int, "x must be typed as int"
    assert annotations.get("y") is int, "y must be typed as int"
    assert annotations.get("z") is int, "z must be typed as int"
