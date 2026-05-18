from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.routing import APIRoute

from controllers.auth_controller import AuthController
from controllers.process_controller import ProcessController
from main import app


FEATURE_PAYLOAD = {
    "type": "Feature",
    "properties": {"name": "Area teste"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[-35.3, -5.9], [-35.2, -5.9], [-35.2, -5.8], [-35.3, -5.9]]],
    },
}


@contextmanager
def override_process_route(route_path: str, controller):
    route = next(
        route for route in app.routes if isinstance(route, APIRoute) and route.path == route_path
    )
    permission_dependency = next(
        dependency.call
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "permission_dependency"
    )

    original_controller_override = app.dependency_overrides.get(ProcessController.inject_controller)
    original_permission_override = app.dependency_overrides.get(permission_dependency)
    original_user_override = app.dependency_overrides.get(AuthController.get_user_from_token)

    async def override_user_dependency():
        return SimpleNamespace(id=uuid4())

    async def permission_override(user=Depends(AuthController.get_user_from_token)):
        return True

    try:
        app.dependency_overrides[ProcessController.inject_controller] = lambda: controller
        app.dependency_overrides[AuthController.get_user_from_token] = override_user_dependency
        app.dependency_overrides[permission_dependency] = permission_override
        yield
    finally:
        if original_controller_override is None:
            app.dependency_overrides.pop(ProcessController.inject_controller, None)
        else:
            app.dependency_overrides[ProcessController.inject_controller] = original_controller_override

        if original_permission_override is None:
            app.dependency_overrides.pop(permission_dependency, None)
        else:
            app.dependency_overrides[permission_dependency] = original_permission_override

        if original_user_override is None:
            app.dependency_overrides.pop(AuthController.get_user_from_token, None)
        else:
            app.dependency_overrides[AuthController.get_user_from_token] = original_user_override


@pytest.mark.anyio
async def test_process_dash_data_returns_plain_json(async_client):
    controller = SimpleNamespace(dash_data=AsyncMock(return_value={"avg": 12.5, "max": 20.1}))

    with override_process_route("/process/dash-data/{energy_type}", controller):
        response = await async_client.post("/process/dash-data/ghi_atlas_m0", json=FEATURE_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {"avg": 12.5, "max": 20.1}
    assert isinstance(response.json(), dict)
    controller.dash_data.assert_awaited_once()


@pytest.mark.anyio
async def test_process_geo_processing_returns_plain_json(async_client):
    controller = SimpleNamespace(
        process_geo_process=AsyncMock(return_value={"properties": {"pixelValues": [[1.0, 2.0, 3.0]]}})
    )

    with override_process_route("/process/geo-processing/{raster_name}", controller):
        response = await async_client.post("/process/geo-processing/ghi_atlas_m0", json=FEATURE_PAYLOAD)

    assert response.status_code == 200
    assert response.json() == {"properties": {"pixelValues": [[1.0, 2.0, 3.0]]}}
    controller.process_geo_process.assert_awaited_once()


@pytest.mark.anyio
async def test_process_raster_returns_plain_json(async_client):
    controller = SimpleNamespace(
        process_raster=AsyncMock(
            return_value={
                "origin": {"lat": -5.0, "lng": -35.0},
                "pixel_size": {"lat": 0.1, "lng": 0.1},
            }
        )
    )

    with override_process_route("/process/raster/{raster_name}", controller):
        response = await async_client.get("/process/raster/ghi_atlas_m0")

    assert response.status_code == 200
    assert response.json() == {
        "origin": {"lat": -5.0, "lng": -35.0},
        "pixel_size": {"lat": 0.1, "lng": 0.1},
    }
    controller.process_raster.assert_awaited_once()


@pytest.mark.anyio
async def test_process_encryption_key_route_not_exposed(async_client):
    response = await async_client.get("/process/encryption-key")

    assert response.status_code == 404