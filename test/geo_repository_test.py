from unittest.mock import AsyncMock, MagicMock

import pytest

from repositories.geo_repository import GeoRepository

test_get_raster_parameters = [
    ('wrong_filename', None, 1, 1, 1, None),
    ('correct_filename', (b'test',), 1, 1, 1, b'test'),
    ('correct_filename_no_list', b'test', 1, 1, 1, 116)
]


@pytest.mark.asyncio
@pytest.mark.parametrize("filename, query_result, x, y, z, expected", test_get_raster_parameters)
async def test_get_raster(filename, query_result, x, y, z, expected):

    # Arrange
    mock_db = MagicMock()
    geo_repository = GeoRepository(db=MagicMock())
    mock_db.fetchone.return_value = (query_result)
    geo_repository.db.execute = AsyncMock(return_value=mock_db)

    # Act
    raster_data = await geo_repository.get_raster(filename, x, y, z)

    # Assert
    assert raster_data == expected

test_get_raster_dataset_parameters = [
    ('wrong_filename', None, None),
    ('correct_filename', (b'test',), b'test'),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("filename, query_result, expected", test_get_raster_dataset_parameters)
async def test_get_raster_dataset(filename, query_result, expected):

    mock_db = MagicMock()
    mock_db.fetchone.return_value = (query_result)
    geo_repository = GeoRepository(db=MagicMock())
    geo_repository.db.execute = AsyncMock(return_value=mock_db)

    raster_data = await geo_repository.get_raster_dataset(filename)

    assert raster_data == expected
