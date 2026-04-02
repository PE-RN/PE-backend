from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute

from controllers.auth_controller import AuthController
from controllers.geo_files_controller import GeoFilesController
from main import app


@pytest.mark.anyio
async def test_post_raster_accepts_authorization_from_header(async_client):

    # Arrange
    controller = SimpleNamespace(upload_raster=AsyncMock(return_value={"table_name": "test_raster", "detail": "Raster importado com sucesso."}))
    route = next(
        route for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/raster/{raster_name}"
    )
    permission_dependency = next(
        dependency.call
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "permission_dependency"
    )
    original_controller_override = app.dependency_overrides.get(GeoFilesController.inject_controller)
    original_permission_override = app.dependency_overrides.get(permission_dependency)
    original_get_user_from_token = AuthController.get_user_from_token

    try:
        app.dependency_overrides[GeoFilesController.inject_controller] = lambda: controller
        AuthController.get_user_from_token = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
        app.dependency_overrides[permission_dependency] = lambda: True

        # Act
        response = await async_client.post(
            "/raster/test_raster",
            headers={"Authorization": "Bearer header-token"},
            files={"file": ("test_raster.tif", b"fake-geotiff", "image/tiff")},
        )

        # Assert
        assert response.status_code == 201
        assert response.json() == {"table_name": "test_raster", "detail": "Raster importado com sucesso."}
        AuthController.get_user_from_token.assert_awaited_once()
        controller.upload_raster.assert_awaited_once()
    finally:
        AuthController.get_user_from_token = original_get_user_from_token
        if original_controller_override is None:
            app.dependency_overrides.pop(GeoFilesController.inject_controller, None)
        else:
            app.dependency_overrides[GeoFilesController.inject_controller] = original_controller_override
        if original_permission_override is None:
            app.dependency_overrides.pop(permission_dependency, None)
        else:
            app.dependency_overrides[permission_dependency] = original_permission_override