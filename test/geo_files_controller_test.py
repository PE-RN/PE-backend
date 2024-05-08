import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.responses import StreamingResponse

from controllers.geo_files_controller import GeoFilesController

test_validate_geofile_parameters = [
    (
        'wrong_table_name',
        'raster',
        None,
        "Geofile não existe!",
        status.HTTP_404_NOT_FOUND,
    ),
    (
        'wrong_name',
        'raster',
        {'name': None, 'geotype': 'raster'},
        "Geofile nome ou tipo faltando!",
        status.HTTP_400_BAD_REQUEST,
    ),
    (
        'wrong_geotype',
        'raster',
        {'name': 'test_tabl e', 'geotype': 'geotype'},
        "Tipo incorreto de geometria!",
        status.HTTP_400_BAD_REQUEST
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("table_name, type, database_return, match, status_code", test_validate_geofile_parameters)
async def test_validate_geofile(table_name, type, database_return, match, status_code):

    # Arrange
    repository = MagicMock()
    repository.get_geofile_by_name = AsyncMock(return_value=database_return)
    geofiles_controller = GeoFilesController(repository=repository)

    # Act
    with pytest.raises(HTTPException, match=match) as error:
        await geofiles_controller._validate_geofile(table_name, type)

    # Assert
    assert error.value.status_code == status_code


test_get_polygon_parameters = [
    ('wrong_table_name', None, None, status.HTTP_404_NOT_FOUND, "Geofile doesn't exist"),
    ('wrong_name', None, {'name': None, 'geotype': 'raster'}, status.HTTP_400_BAD_REQUEST, "Geofile name or type is missing"),
    ('wrong_geotype', None, {'name': 'test_table', 'geotype': None}, status.HTTP_400_BAD_REQUEST, "Geofile name or type is missing")
]


@pytest.mark.asyncio
async def test_get_polygon():

    # Arrange
    polygon = {'name': 'test_table', 'geotype': None}
    mock_repository = MagicMock()
    geo_controller = GeoFilesController(repository=mock_repository)
    mock_repository.get_polygon_by_name = AsyncMock(return_value=polygon)
    geo_controller._validate_geofile = AsyncMock(return_value=None)

    # Act
    raster_data = await geo_controller.get_polygon('table_name')

    # Assert
    assert raster_data == polygon


@pytest.mark.asyncio
async def test_get_polygon_wrong():

    # Arrange
    geo_controller = GeoFilesController(repository=MagicMock())
    geo_controller._validate_geofile = AsyncMock(return_value=None)
    geo_controller.repository.get_polygon = lambda: (_ for _ in ()).throw(Exception(""))

    # Act
    with pytest.raises(Exception, match="") as error:
        await geo_controller.get_polygon('table_name')

    # Assert
    assert error.value.status_code == 500


@pytest.mark.asyncio
async def test_get_raster():

    # Arrange
    file = open("example.txt", "w")
    geo_files_controller = GeoFilesController(repository=MagicMock())
    geo_files_controller._validate_geofile = AsyncMock(return_value=None)
    geo_files_controller.repository.get_raster = AsyncMock(return_value=file)
    raster_response = StreamingResponse(
        file,
        media_type="image/png",
        headers={"Content-Disposition": "attachment; filename=raster.png"}
    )

    # Act
    raster_data = await geo_files_controller.get_raster('table', 1, 1, 1)

    # Assert
    assert type(raster_data) is type(raster_response)

    # Tear down
    os.remove("example.txt")
