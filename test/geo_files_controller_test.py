from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.responses import StreamingResponse

from controllers.geo_files_controller import GeoFilesController

test_validate_geofile_parameters = [
    ('wrong_table_name', 'raster', None, (True, {"Bad Request": "Geofile doesn't exist"})),
    ('wrong_name', 'raster', {'name': None, 'geotype': 'raster'}, (True, {"Bad Request": "Geofile name or type is missing"})),
    ('wrong_geotype', 'raster', {'name': 'test_table', 'geotype': None}, (True, {"Bad Request": "Geofile name or type is missing"})),
    ('wrong_geotype', 'raster', {'name': 'test_table', 'geotype': 'polygon'}, (True, {"Bad Request": "Incorrect type of geometry"})),
    ('table_name', 'polygon', {'name': 'test_table', 'geotype': 'polygon'}, (False, None)),
    ('table_name', 'raster', {'name': 'test_table', 'geotype': 'raster'}, (False, None))
]

@pytest.mark.asyncio
@pytest.mark.parametrize("table_name, type, database_return, expected", test_validate_geofile_parameters)
async def test_validate_geofile(table_name, type, database_return, expected):
    mock_repository = AsyncMock()
    mock_repository.validade_geofile.return_value = database_return


    your_object = GeoFilesController(repository=mock_repository)

    raster_data = await your_object._validate_geofile(table_name, type)
    assert raster_data == expected

test_get_polygon_parameters = [
    ('wrong_table_name', None, None, {"Bad Request": "Geofile doesn't exist"}),
    ('wrong_name', None, {'name': None, 'geotype': 'raster'}, {"Bad Request": "Geofile name or type is missing"}),
    ('wrong_geotype', None, {'name': 'test_table', 'geotype': None}, {"Bad Request": "Geofile name or type is missing"}),
    ('table_name', None, {'name': 'test_table', 'geotype': 'polygon'}, None),
    ('table_name', None, {'name': 'test_table', 'geotype': 'raster'}, {"Bad Request": "Incorrect type of geometry"}),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("table_name, polygon, validation_return, expected", test_get_polygon_parameters)
async def test_get_polygon(table_name, polygon, validation_return, expected):
    mock_repository = AsyncMock()
    mock_repository.validade_geofile.return_value = validation_return
    mock_repository.get_polygon.return_value = polygon
    mock_response = MagicMock()


    your_object = GeoFilesController(repository=mock_repository)

    raster_data = await your_object.get_polygon(table_name, mock_response)
    assert raster_data == expected

raster_response = StreamingResponse(
                None,
                media_type="image/png",
                headers={"Content-Disposition": "attachment; filename=raster.png"}
            ),
test_get_raster_parameters = [
    ('wrong_table_name', None, None, {"Bad Request": "Geofile doesn't exist"}),
    ('wrong_name', None, {'name': None, 'geotype': 'raster'}, {"Bad Request": "Geofile name or type is missing"}),
    ('wrong_geotype', None, {'name': 'test_table', 'geotype': None}, {"Bad Request": "Geofile name or type is missing"}),
    ('table_name', None, {'name': 'test_table', 'geotype': 'polygon'}, {"Bad Request": "Incorrect type of geometry"}),
    ('table_name', None, {'name': 'test_table', 'geotype': 'raster'}, raster_response[0])
]

@pytest.mark.asyncio
@pytest.mark.parametrize("table_name, raster, validation_return, expected", test_get_raster_parameters)
async def test_get_raster(table_name, raster, validation_return, expected):
    mock_repository = AsyncMock()
    mock_repository.validade_geofile.return_value = validation_return
    mock_repository.get_raster.return_value = raster
    mock_response = MagicMock()


    your_object = GeoFilesController(repository=mock_repository)

    raster_data = await your_object.get_raster(table_name, mock_response, 1, 1, 1)
    assert type(raster_data) == type(expected)
