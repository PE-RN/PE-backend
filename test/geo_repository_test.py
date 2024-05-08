import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from osgeo import gdal

from repositories.geo_repository import GeoRepository

test_get_raster_parameters = [
    ('wrong_filename', None, 1, 1, 1, None),
    ('correct_filename', (b'test',), 1, 1, 1, b'test'),
    ('correct_filename_no_list', b'test', 1, 1, 1, 116)
]


@pytest.mark.asyncio
@pytest.mark.parametrize("filename, query_result, x, y, z, expected", test_get_raster_parameters)
async def test_get_raster(filename, query_result, x, y, z, expected):
    # Mocking the necessary dependencies
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (query_result)
    mock_db.execute.return_value = mock_result
    mock_db.execute.return_value.fetchone.return_value = query_result

    your_object = GeoRepository(db=mock_db)

    # Testing the method
    raster_data = await your_object.get_raster(filename, x, y, z)
    assert raster_data == expected

test_get_raster_dataset_parameters = [
    ('wrong_filename', None, 'dataset', None),
    ('correct_filename', (b'test',), 'dataset', 'dataset'),
    ('correct_filename_no_list', b'test', 'dataset', None)
]


@pytest.mark.asyncio
@pytest.mark.parametrize("filename, query_result, dataset, expected", test_get_raster_dataset_parameters)
async def test_get_raster_dataset(filename, query_result, dataset, expected):
    # Mocking the necessary dependencies
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.fetchone.return_value = (query_result)
    mock_db.execute.return_value = mock_result
    mock_db.execute.return_value.fetchone.return_value = query_result

    mock_gdal_open = MagicMock()
    mock_gdal_open.return_value = dataset
    gdal.Open = mock_gdal_open
    mock_os_remove = MagicMock()
    os.remove = mock_os_remove

    your_object = GeoRepository(db=mock_db)

    # Testing the method
    raster_data = await your_object.get_raster_dataset(filename)
    assert raster_data == expected
