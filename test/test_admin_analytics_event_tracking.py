from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from os import getenv
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.routing import APIRoute
from jose import jwt
from sqlmodel import delete, select

from controllers.auth_controller import AuthController
from main import BACKEND_ROOT, app
from sql_app import models
from test.conftest import TesteSessionLocal


def _build_auth_header(email: str) -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": email,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        },
        getenv("SECRET_KEY"),
        algorithm=getenv("ALGORITHM"),
    )
    return {"Authorization": f"{getenv('TOKEN_TYPE', 'Bearer')} {token}"}


async def _load_recent_events(created_after: datetime) -> list[models.AdminAnalyticsEvent]:
    async with TesteSessionLocal() as db:
        result = await db.exec(
            select(models.AdminAnalyticsEvent)
            .where(models.AdminAnalyticsEvent.created_at >= created_after)
            .order_by(models.AdminAnalyticsEvent.created_at.asc())
        )
        return list(result.all())


async def _delete_events(events: list[models.AdminAnalyticsEvent]) -> None:
    if not events:
        return

    async with TesteSessionLocal() as db:
        await db.exec(delete(models.AdminAnalyticsEvent).where(models.AdminAnalyticsEvent.id.in_([event.id for event in events])))
        await db.commit()


async def _delete_feedback(feedback_id: UUID | None) -> None:
    if feedback_id is None:
        return

    async with TesteSessionLocal() as db:
        await db.exec(delete(models.Feedback).where(models.Feedback.id == feedback_id))
        await db.commit()


def _resolve_backend_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None

    path = Path(path_value)
    if path.is_absolute():
        return path

    return (BACKEND_ROOT / path).resolve()


@pytest.fixture
def override_auth():
    original_override = app.dependency_overrides.get(AuthController.get_user_from_token)

    def apply(user=None, side_effect=None):
        async def _override():
            if side_effect is not None:
                raise side_effect
            return user

        app.dependency_overrides[AuthController.get_user_from_token] = _override

    yield apply
    if original_override is None:
        app.dependency_overrides.pop(AuthController.get_user_from_token, None)
    else:
        app.dependency_overrides[AuthController.get_user_from_token] = original_override


@pytest.fixture
async def seeded_admin_user():
    suffix = uuid4().hex[:8]
    admin_group = models.Group(
        id=uuid4(),
        name="admin",
        description=f"Administradores tracking {suffix}",
    )
    admin_user = models.User(
        id=uuid4(),
        created_at=datetime(2026, 5, 10, 8, 0),
        updated_at=datetime(2026, 5, 10, 8, 0),
        email=f"tracking-admin-{suffix}@example.com",
        password="secret",
        ocupation="gestor",
        group_id=admin_group.id,
        gender="feminino",
        education="superior",
        institution="Equipe Tracking",
        age="35",
        user="Equipe Tracking",
    )

    async with TesteSessionLocal() as db:
        db.add(admin_group)
        await db.commit()

        db.add(admin_user)
        await db.commit()

    try:
        yield {"admin_group": admin_group, "admin_user": admin_user}
    finally:
        async with TesteSessionLocal() as db:
            await db.exec(delete(models.User).where(models.User.id == admin_user.id))
            await db.exec(delete(models.Group).where(models.Group.id == admin_group.id))
            await db.commit()


@pytest.mark.anyio
async def test_check_token_persists_user_activity_and_system_health(async_client, seeded_admin_user):
    created_after = datetime.utcnow()

    response = await async_client.get(
        "/check-token",
        headers=_build_auth_header(seeded_admin_user["admin_user"].email),
    )

    events = await _load_recent_events(created_after)
    try:
        assert response.status_code == 200
        assert len(events) == 2

        user_event = next(event for event in events if event.domain == "user-activity")
        system_event = next(event for event in events if event.domain == "system-health")

        assert user_event.event_type == "check-token"
        assert user_event.actor_user_id == seeded_admin_user["admin_user"].id
        assert user_event.actor_name == seeded_admin_user["admin_user"].user
        assert user_event.target_type == "user"
        assert user_event.status == "success"

        assert system_event.label == "/check-token"
        assert system_event.status_code == 200
        assert system_event.endpoint_key == "check-token-list"
    finally:
        await _delete_events(events)


@pytest.mark.anyio
async def test_contact_persists_admin_operation_and_system_health(async_client):
    created_after = datetime.utcnow()
    feedback_id = None

    response = await async_client.post(
        "/contact",
        json={
            "name": "Equipe Teste",
            "email": "tracking@example.com",
            "message": "Verificando rastreamento",
            "platform_rate": 5,
            "intuitivity": 4,
            "type": "contato",
        },
    )

    if response.status_code == 200:
        feedback_id = UUID(response.json()["id"])

    events = await _load_recent_events(created_after)
    try:
        assert response.status_code == 200
        assert len(events) == 2

        operation_event = next(event for event in events if event.domain == "admin-operations")
        system_event = next(event for event in events if event.domain == "system-health")

        assert operation_event.event_type == "feedback-submit"
        assert operation_event.label == "Envio de feedback"
        assert operation_event.target_type == "feedback"
        assert operation_event.status == "success"

        assert system_event.label == "/contact"
        assert system_event.endpoint_key == "contact-create"
        assert system_event.status_code == 200
    finally:
        await _delete_events(events)
        await _delete_feedback(feedback_id)


@pytest.mark.anyio
async def test_admin_analytics_route_persists_only_system_health(async_client, override_auth, seeded_admin_user):
    override_auth(user=seeded_admin_user["admin_user"])
    created_after = datetime.utcnow()

    response = await async_client.get(
        "/admin-analytics/filter-options",
        params={"scope": "all"},
    )

    events = await _load_recent_events(created_after)
    try:
        assert response.status_code == 200
        assert len(events) == 1
        assert events[0].domain == "system-health"
        assert events[0].label == "/admin-analytics/filter-options"
        assert events[0].endpoint_key == "admin-analytics-filter-options-list"
    finally:
        await _delete_events(events)


@pytest.mark.anyio
async def test_layer_create_persists_layer_id_and_upload_details(async_client, override_auth, seeded_admin_user):
    created_after = datetime.utcnow()
    events: list[models.AdminAnalyticsEvent] = []
    created_layer_id: UUID | None = None
    layer_group = models.LayerGroups(id=uuid4(), name=f"Grupo Camada {uuid4().hex[:8]}")
    route = next(
        route for route in app.routes if isinstance(route, APIRoute) and route.path == "/layer"
    )
    permission_dependency = next(
        dependency.call
        for dependency in route.dependant.dependencies
        if getattr(dependency.call, "__name__", "") == "permission_dependency"
    )
    original_permission_override = app.dependency_overrides.get(permission_dependency)

    try:
        async with TesteSessionLocal() as db:
            db.add(layer_group)
            await db.commit()

        override_auth(user=seeded_admin_user["admin_user"])

        async def permission_override():
            return True

        app.dependency_overrides[permission_dependency] = permission_override

        response = await async_client.post(
            "/layer",
            data={
                "name": "Camada Teste Analytics",
                "subtitle": "Fonte Teste, 2026",
                "layer_group_id": str(layer_group.id),
                "activated": "true",
            },
            files={
                "file": (
                    "camada_teste.geojson",
                    json.dumps(
                        {
                            "type": "FeatureCollection",
                            "features": [
                                {
                                    "type": "Feature",
                                    "properties": {"nome": "A"},
                                    "geometry": {
                                        "type": "Point",
                                        "coordinates": [-35.2, -5.8],
                                    },
                                }
                            ],
                        }
                    ).encode("utf-8"),
                    "application/geo+json",
                ),
                "file_icon": (
                    "camada_teste.svg",
                    b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40"></svg>',
                    "image/svg+xml",
                ),
            },
        )

        events = await _load_recent_events(created_after)

        assert response.status_code == 200
        body = response.json()
        created_layer_id = UUID(body["id"])

        operation_event = next(
            event
            for event in events
            if event.domain == "admin-operations" and event.endpoint_key == "layer-create"
        )

        assert operation_event.target_id == str(created_layer_id)
        assert operation_event.layer_id == created_layer_id
        assert operation_event.payload["group_id"] == str(layer_group.id)
        assert operation_event.payload["layer_name"] == "Camada Teste Analytics"
        assert operation_event.payload["details"]["feature_count"] == 1
        assert set(operation_event.payload["details"]["geometry_types"]) == {"Point"}
        assert "/" in body["path"]
        assert "/" in body["path_icon"]
    finally:
        await _delete_events(events)

        async with TesteSessionLocal() as db:
            if created_layer_id is not None:
                layer = await db.get(models.Layer, created_layer_id)
                if layer is not None:
                    await db.delete(layer)
            group = await db.get(models.LayerGroups, layer_group.id)
            if group is not None:
                await db.delete(group)
            await db.commit()

        for path_value in (
            response.json().get("path") if 'response' in locals() and response.status_code == 200 else None,
            response.json().get("path_icon") if 'response' in locals() and response.status_code == 200 else None,
        ):
            file_path = _resolve_backend_path(path_value)
            if file_path and file_path.exists():
                file_path.unlink()

        if original_permission_override is None:
            app.dependency_overrides.pop(permission_dependency, None)
        else:
            app.dependency_overrides[permission_dependency] = original_permission_override


@pytest.mark.anyio
async def test_sidebar_upload_preview_persists_map_usage_event(async_client, override_auth, seeded_admin_user):
    created_after = datetime.utcnow()

    override_auth(user=seeded_admin_user["admin_user"])

    response = await async_client.post(
        "/layer/upload-preview",
        json={
            "file_name": "camada_local.geojson",
            "feature_count": 2,
            "geometry_types": ["Polygon", "Point", "Polygon"],
            "geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"name": "area-a"},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                        },
                    },
                    {
                        "type": "Feature",
                        "properties": {"name": "point-b"},
                        "geometry": {
                            "type": "Point",
                            "coordinates": [2, 3],
                        },
                    },
                ],
            },
        },
    )

    events = await _load_recent_events(created_after)
    try:
        assert response.status_code == 204

        upload_event = next(
            event
            for event in events
            if event.domain == "map-usage" and event.event_type == "upload-preview"
        )

        assert upload_event.actor_user_id == seeded_admin_user["admin_user"].id
        assert upload_event.target_type == "uploaded-layer"
        assert upload_event.payload["layer_name"] == "camada_local.geojson"
        assert upload_event.payload["details"]["feature_count"] == 2
        assert upload_event.payload["details"]["geometry_types"] == ["Point", "Polygon"]
        assert upload_event.payload["geojson"] == {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"name": "area-a"},
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
                    },
                },
                {
                    "type": "Feature",
                    "properties": {"name": "point-b"},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [2, 3],
                    },
                },
            ],
        }
    finally:
        await _delete_events(events)