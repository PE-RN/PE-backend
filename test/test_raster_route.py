from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from controllers.auth_controller import AuthController
from controllers.geo_files_controller import GeoFilesController
from main import app


@pytest.mark.anyio
async def test_post_raster_accepts_authorization_from_form(async_client):

    # Arrange
    controller = SimpleNamespace(upload_raster=AsyncMock(return_value={"table_name": "test_raster", "detail": "Raster importado com sucesso."}))
    auth_repository = SimpleNamespace()
    original_controller_override = app.dependency_overrides.get(GeoFilesController.inject_controller)
    original_repository_override = app.dependency_overrides.get(AuthController.inject_repository)
    original_get_user_from_token = AuthController.get_user_from_token
    original_user_has_permission = AuthController.user_has_permission

    try:
        app.dependency_overrides[GeoFilesController.inject_controller] = lambda: controller
        app.dependency_overrides[AuthController.inject_repository] = lambda: auth_repository
        AuthController.get_user_from_token = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        AuthController.user_has_permission = AsyncMock(return_value=True)

        # Act
        response = await async_client.post(
            "/raster/test_raster",
            data={"authorization": "Bearer form-token"},
            files={"file": ("test_raster.tif", b"fake-geotiff", "image/tiff")},
        )

        # Assert
        assert response.status_code == 201
        assert response.json() == {"table_name": "test_raster", "detail": "Raster importado com sucesso."}
        AuthController.get_user_from_token.assert_awaited_once_with(auth_repository, "Bearer form-token")
        AuthController.user_has_permission.assert_awaited_once()
        controller.upload_raster.assert_awaited_once()
    finally:
        AuthController.get_user_from_token = original_get_user_from_token
        AuthController.user_has_permission = original_user_has_permission
        if original_controller_override is None:
            app.dependency_overrides.pop(GeoFilesController.inject_controller, None)
        else:
            app.dependency_overrides[GeoFilesController.inject_controller] = original_controller_override
        if original_repository_override is None:
            app.dependency_overrides.pop(AuthController.inject_repository, None)
        else:
            app.dependency_overrides[AuthController.inject_repository] = original_repository_override