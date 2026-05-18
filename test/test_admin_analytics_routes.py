from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from fastapi import HTTPException, status
from sqlmodel import delete, select

from controllers.auth_controller import AuthController
from main import app
from sql_app import models
from test.conftest import TesteSessionLocal


def _dt(year: int, month: int, day: int, hour: int = 10, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute)


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


@pytest.fixture(autouse=True)
async def cleanup_runtime_analytics_rows():
    async with TesteSessionLocal() as db:
        existing_event_ids = set((await db.exec(select(models.AdminAnalyticsEvent.id))).all())
        existing_export_ids = set((await db.exec(select(models.AdminAnalyticsExport.id))).all())

    yield

    async with TesteSessionLocal() as db:
        current_event_ids = set((await db.exec(select(models.AdminAnalyticsEvent.id))).all())
        current_export_ids = set((await db.exec(select(models.AdminAnalyticsExport.id))).all())

        new_event_ids = list(current_event_ids - existing_event_ids)
        new_export_ids = list(current_export_ids - existing_export_ids)

        if new_event_ids:
            await db.exec(delete(models.AdminAnalyticsEvent).where(models.AdminAnalyticsEvent.id.in_(new_event_ids)))
        if new_export_ids:
            await db.exec(delete(models.AdminAnalyticsExport).where(models.AdminAnalyticsExport.id.in_(new_export_ids)))

        await db.commit()


@pytest.fixture
async def seed_factory():
    cleanup: dict[type, list] = {
        models.AdminAnalyticsEvent: [],
        models.AdminAnalyticsExport: [],
        models.Layer: [],
        models.LayerGroups: [],
        models.PdfFile: [],
        models.User: [],
        models.Group: [],
    }

    async def _seed(include_events: bool = False) -> dict[str, object]:
        suffix = uuid4().hex[:8]

        admin_group = models.Group(
            id=uuid4(),
            name="admin",
            description=f"Administradores analytics {suffix}",
        )
        viewer_group = models.Group(
            id=uuid4(),
            name=f"viewer-{suffix}",
            description=f"Visualizadores analytics {suffix}",
        )

        admin_user = models.User(
            id=uuid4(),
            created_at=_dt(2026, 5, 10, 8, 0),
            updated_at=_dt(2026, 5, 14, 8, 15),
            email=f"admin-{suffix}@example.com",
            password="secret",
            ocupation="gestor",
            group_id=admin_group.id,
            gender="feminino",
            education="superior",
            institution="Equipe Admin",
            age="35",
            user="Equipe Admin",
        )
        viewer_user = models.User(
            id=uuid4(),
            created_at=_dt(2026, 5, 11, 9, 30),
            updated_at=_dt(2026, 5, 14, 10, 0),
            email=f"maria-{suffix}@example.com",
            password="secret",
            ocupation="pesquisador",
            group_id=viewer_group.id,
            gender="feminino",
            education="mestrado",
            institution="SENAI",
            age="29",
            user="Maria Silva",
        )
        another_user = models.User(
            id=uuid4(),
            created_at=_dt(2026, 4, 15, 11, 0),
            updated_at=_dt(2026, 5, 2, 7, 30),
            email=f"joao-{suffix}@example.com",
            password="secret",
            ocupation="docente",
            group_id=viewer_group.id,
            gender="masculino",
            education="doutorado",
            institution="UFRN",
            age="41",
            user="João Lima",
        )

        layer_group = models.LayerGroups(
            id=uuid4(),
            created_at=_dt(2026, 5, 1, 9, 0),
            updated_at=_dt(2026, 5, 1, 9, 0),
            name="Infraestrutura",
            layer_group_id=None,
        )
        layer = models.Layer(
            id=uuid4(),
            created_at=_dt(2026, 5, 13, 7, 45),
            updated_at=_dt(2026, 5, 13, 7, 45),
            name="Aerodromos",
            subtitle="Infraestrutura aeroportuária",
            path="/layers/aerodromos.geojson",
            path_icon="/icons/aerodromos.svg",
            activated=True,
            layer_group_id=layer_group.id,
        )
        pdf_file = models.PdfFile(
            id=uuid4(),
            created_at=_dt(2026, 5, 12, 10, 22),
            updated_at=_dt(2026, 5, 12, 10, 22),
            name="Relatorio Solar",
            path="/files/solar.pdf",
            category="Mapa",
            sub_category="Solar",
        )
        other_file = models.PdfFile(
            id=uuid4(),
            created_at=_dt(2026, 3, 5, 8, 10),
            updated_at=_dt(2026, 3, 5, 8, 10),
            name="Boletim Eolico",
            path="/files/wind.pdf",
            category="Boletim",
            sub_category="Eolico",
        )

        async with TesteSessionLocal() as db:
            db.add_all([admin_group, viewer_group, layer_group])
            await db.commit()

            db.add_all([admin_user, viewer_user, another_user, layer, pdf_file, other_file])
            await db.commit()

            cleanup[models.Group].extend([admin_group.id, viewer_group.id])
            cleanup[models.User].extend([admin_user.id, viewer_user.id, another_user.id])
            cleanup[models.LayerGroups].append(layer_group.id)
            cleanup[models.Layer].append(layer.id)
            cleanup[models.PdfFile].extend([pdf_file.id, other_file.id])

            result: dict[str, object] = {
                "admin_group": admin_group,
                "viewer_group": viewer_group,
                "admin_user": admin_user,
                "viewer_user": viewer_user,
                "another_user": another_user,
                "layer_group": layer_group,
                "layer": layer,
                "pdf_file": pdf_file,
                "other_file": other_file,
            }

            if include_events:
                login_viewer = models.AdminAnalyticsEvent(
                    id=uuid4(),
                    created_at=_dt(2026, 5, 14, 8, 15),
                    updated_at=_dt(2026, 5, 14, 8, 15),
                    domain="user-activity",
                    event_type="login",
                    label="Login realizado",
                    occurred_at=_dt(2026, 5, 14, 8, 15),
                    actor_user_id=viewer_user.id,
                    actor_name=viewer_user.user,
                    payload={"detail": "Acesso ao painel"},
                )
                login_another = models.AdminAnalyticsEvent(
                    id=uuid4(),
                    created_at=_dt(2026, 5, 10, 9, 0),
                    updated_at=_dt(2026, 5, 10, 9, 0),
                    domain="user-activity",
                    event_type="login",
                    label="Login realizado",
                    occurred_at=_dt(2026, 5, 10, 9, 0),
                    actor_user_id=another_user.id,
                    actor_name=another_user.user,
                    payload={"detail": "Acesso externo"},
                )
                file_download = models.AdminAnalyticsEvent(
                    id=uuid4(),
                    created_at=_dt(2026, 5, 14, 10, 22),
                    updated_at=_dt(2026, 5, 14, 10, 22),
                    domain="file-usage",
                    event_type="download",
                    label="Download de relatorio",
                    occurred_at=_dt(2026, 5, 14, 10, 22),
                    actor_user_id=viewer_user.id,
                    actor_name=viewer_user.user,
                    file_id=pdf_file.id,
                    payload={
                        "file_name": pdf_file.name,
                        "category": pdf_file.category,
                        "sub_category": pdf_file.sub_category,
                        "detail": "Relatorio solar",
                    },
                )
                map_view = models.AdminAnalyticsEvent(
                    id=uuid4(),
                    created_at=_dt(2026, 5, 14, 9, 45),
                    updated_at=_dt(2026, 5, 14, 9, 45),
                    domain="map-usage",
                    event_type="view",
                    label="Visualizacao de camada",
                    occurred_at=_dt(2026, 5, 14, 9, 45),
                    actor_user_id=viewer_user.id,
                    actor_name=viewer_user.user,
                    layer_id=layer.id,
                    payload={
                        "layer_name": layer.name,
                        "group_id": str(layer_group.id),
                        "group_name": layer_group.name,
                        "theme": "infraestrutura",
                        "raster_name": "solar-2026",
                        "search_term": "Aero",
                    },
                )
                admin_error = models.AdminAnalyticsEvent(
                    id=uuid4(),
                    created_at=_dt(2026, 5, 14, 10, 30),
                    updated_at=_dt(2026, 5, 14, 10, 30),
                    domain="admin-operations",
                    event_type="user-update",
                    label="Atualizacao de usuario",
                    occurred_at=_dt(2026, 5, 14, 10, 30),
                    actor_user_id=admin_user.id,
                    actor_name=admin_user.user,
                    target_type="user",
                    target_id=str(viewer_user.id),
                    status="error",
                    payload={"target_label": viewer_user.user, "detail": "Falha na atualização do usuário"},
                )
                admin_related = models.AdminAnalyticsEvent(
                    id=uuid4(),
                    created_at=_dt(2026, 5, 14, 10, 35),
                    updated_at=_dt(2026, 5, 14, 10, 35),
                    domain="admin-operations",
                    event_type="user-update",
                    label="Atualizacao de usuario",
                    occurred_at=_dt(2026, 5, 14, 10, 35),
                    actor_user_id=admin_user.id,
                    actor_name=admin_user.user,
                    target_type="user",
                    target_id=str(viewer_user.id),
                    status="success",
                    payload={"target_label": viewer_user.user, "detail": "Atualização concluída"},
                )
                system_ok = models.AdminAnalyticsEvent(
                    id=uuid4(),
                    created_at=_dt(2026, 5, 14, 10, 0),
                    updated_at=_dt(2026, 5, 14, 10, 0),
                    domain="system-health",
                    event_type="request",
                    label="/file",
                    occurred_at=_dt(2026, 5, 14, 10, 0),
                    endpoint_key="file-list",
                    method="GET",
                    status_code=200,
                    latency_ms=120,
                    payload={"label": "/file"},
                )
                system_error = models.AdminAnalyticsEvent(
                    id=uuid4(),
                    created_at=_dt(2026, 5, 14, 10, 5),
                    updated_at=_dt(2026, 5, 14, 10, 5),
                    domain="system-health",
                    event_type="request",
                    label="/file",
                    occurred_at=_dt(2026, 5, 14, 10, 5),
                    endpoint_key="file-list",
                    method="GET",
                    status_code=500,
                    latency_ms=620,
                    payload={"label": "/file", "detail": "Timeout no backend"},
                )
                db.add_all([
                    login_viewer,
                    login_another,
                    file_download,
                    map_view,
                    admin_error,
                    admin_related,
                    system_ok,
                    system_error,
                ])
                await db.commit()
                cleanup[models.AdminAnalyticsEvent].extend(
                    [
                        login_viewer.id,
                        login_another.id,
                        file_download.id,
                        map_view.id,
                        admin_error.id,
                        admin_related.id,
                        system_ok.id,
                        system_error.id,
                    ]
                )
                result.update(
                    {
                        "admin_error": admin_error,
                        "admin_related": admin_related,
                    }
                )

        return result

    yield _seed

    async with TesteSessionLocal() as db:
        for model in (
            models.AdminAnalyticsEvent,
            models.AdminAnalyticsExport,
            models.Layer,
            models.LayerGroups,
            models.PdfFile,
            models.User,
            models.Group,
        ):
            ids = cleanup[model]
            if ids:
                await db.exec(delete(model).where(model.id.in_(ids)))
        await db.commit()


@pytest.mark.anyio
async def test_admin_analytics_filter_options_returns_expected_contract(async_client, override_auth, seed_factory):
    seeded = await seed_factory(include_events=True)
    override_auth(user=seeded["admin_user"])

    response = await async_client.get("/admin-analytics/filter-options", params={"scope": "all"})

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert set(body.keys()) == {
        "date_presets",
        "granularities",
        "file_categories",
        "file_subcategories",
        "layer_groups",
        "layers",
        "admin_users",
        "system_endpoints",
        "status_codes",
    }
    assert {item["value"] for item in body["file_categories"]} == {"Boletim", "Mapa"}
    assert {item["name"] for item in body["layer_groups"]} == {"Infraestrutura"}
    assert {item["name"] for item in body["admin_users"]} == {"Equipe Admin"}
    assert any(item["key"] == "file-list" for item in body["system_endpoints"])
    assert 500 in body["status_codes"]


@pytest.mark.anyio
async def test_admin_analytics_returns_401_when_token_is_invalid(async_client, override_auth):
    override_auth(side_effect=HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido!"))

    response = await async_client.get("/admin-analytics/overview")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Token inválido!"


@pytest.mark.anyio
async def test_admin_analytics_returns_403_for_non_admin_user(async_client, override_auth, seed_factory):
    seeded = await seed_factory()
    override_auth(user=seeded["viewer_user"])

    response = await async_client.get("/admin-analytics/overview")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Não possui permissão administrativa."


@pytest.mark.anyio
async def test_admin_analytics_returns_422_with_contract_shape(async_client, override_auth, seed_factory):
    seeded = await seed_factory()
    override_auth(user=seeded["admin_user"])

    response = await async_client.get(
        "/admin-analytics/overview",
        params={"date_from": "2026-05-20", "date_to": "2026-05-01"},
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    body = response.json()
    assert set(body.keys()) == {"detail", "errors"}
    assert body["detail"] == "Filtros inválidos"
    assert isinstance(body["errors"], list)
    assert {"field", "message"}.issubset(body["errors"][0].keys())


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path,params,expected_top_level,rows_path",
    [
        (
            "/admin-analytics/overview",
            {"date_from": "2026-01-01", "date_to": "2026-01-02"},
            {"summary_cards", "tab_counts", "alerts", "recent_activity", "last_updated_at"},
            None,
        ),
        (
            "/admin-analytics/user-activity",
            {"date_from": "2026-01-01", "date_to": "2026-01-02"},
            {"summary_cards", "timeseries", "breakdowns", "table", "last_updated_at"},
            ["table", "rows"],
        ),
        (
            "/admin-analytics/file-usage",
            {"date_from": "2026-01-01", "date_to": "2026-01-02"},
            {"summary_cards", "timeseries", "breakdowns", "table", "last_updated_at"},
            ["table", "rows"],
        ),
        (
            "/admin-analytics/map-usage",
            {"date_from": "2026-01-01", "date_to": "2026-01-02"},
            {"summary_cards", "timeseries", "breakdowns", "table", "last_updated_at"},
            ["table", "rows"],
        ),
        (
            "/admin-analytics/admin-operations",
            {"date_from": "2026-01-01", "date_to": "2026-01-02"},
            {"summary_cards", "timeseries", "breakdowns", "table", "last_updated_at"},
            ["table", "rows"],
        ),
        (
            "/admin-analytics/system-health",
            {"endpoint": "missing"},
            {"summary_cards", "timeseries", "status_breakdown", "latency_buckets", "table", "last_updated_at"},
            ["table", "rows"],
        ),
    ],
)
async def test_admin_analytics_empty_domains_return_valid_schema(
    async_client,
    override_auth,
    seed_factory,
    path,
    params,
    expected_top_level,
    rows_path,
):
    seeded = await seed_factory()
    override_auth(user=seeded["admin_user"])

    response = await async_client.get(path, params=params)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert set(body.keys()) == expected_top_level
    if rows_path:
        rows = body
        for key in rows_path:
            rows = rows[key]
        assert rows == []


@pytest.mark.anyio
async def test_admin_analytics_applies_global_and_domain_filters(async_client, override_auth, seed_factory):
    seeded = await seed_factory(include_events=True)
    override_auth(user=seeded["admin_user"])

    user_response = await async_client.get(
        "/admin-analytics/user-activity",
        params={"date_from": "2026-05-01", "date_to": "2026-05-31", "institution": "SENAI"},
    )
    file_response = await async_client.get(
        "/admin-analytics/file-usage",
        params={
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
            "category": "Mapa",
            "search": "Solar",
            "page": 1,
            "page_size": 1,
            "sort_by": "file_name",
            "sort_order": "asc",
        },
    )
    map_response = await async_client.get(
        "/admin-analytics/map-usage",
        params={
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
            "layer_group_id": str(seeded["layer_group"].id),
            "search_term": "Aero",
        },
    )
    ops_response = await async_client.get(
        "/admin-analytics/admin-operations",
        params={"date_from": "2026-05-01", "date_to": "2026-05-31", "status": "error"},
    )
    system_response = await async_client.get(
        "/admin-analytics/system-health",
        params={"endpoint": "file-list", "method": "GET"},
    )

    assert user_response.status_code == status.HTTP_200_OK
    assert user_response.json()["table"]["total_rows"] == 1
    assert user_response.json()["table"]["rows"][0]["institution"] == "SENAI"

    assert file_response.status_code == status.HTTP_200_OK
    assert file_response.json()["table"]["total_rows"] == 1
    assert file_response.json()["table"]["rows"][0]["file_name"] == "Relatorio Solar"
    assert set(file_response.json()["table"]["rows"][0].keys()) == {
        "file_id",
        "file_name",
        "category",
        "sub_category",
        "created_at",
        "downloads",
        "unique_users",
        "last_download_at",
    }

    assert map_response.status_code == status.HTTP_200_OK
    assert map_response.json()["table"]["total_rows"] == 1
    assert map_response.json()["table"]["rows"][0]["group_name"] == "Infraestrutura"

    assert ops_response.status_code == status.HTTP_200_OK
    assert ops_response.json()["table"]["total_rows"] == 1
    assert ops_response.json()["table"]["rows"][0]["status"] == "error"

    assert system_response.status_code == status.HTTP_200_OK
    assert system_response.json()["table"]["total_rows"] == 1
    assert system_response.json()["table"]["rows"][0]["endpoint_key"] == "file-list"


@pytest.mark.anyio
async def test_admin_analytics_detail_routes_return_expected_entities(async_client, override_auth, seed_factory):
    seeded = await seed_factory(include_events=True)
    override_auth(user=seeded["admin_user"])

    user_response = await async_client.get(f"/admin-analytics/user-activity/{seeded['viewer_user'].id}")
    file_response = await async_client.get(f"/admin-analytics/file-usage/{seeded['pdf_file'].id}")
    layer_response = await async_client.get(f"/admin-analytics/map-usage/{seeded['layer'].id}")
    event_response = await async_client.get(f"/admin-analytics/admin-operations/{seeded['admin_error'].id}")
    endpoint_response = await async_client.get("/admin-analytics/system-health/file-list")

    assert user_response.status_code == status.HTTP_200_OK
    assert user_response.json()["user"]["id"] == str(seeded["viewer_user"].id)
    assert set(user_response.json()["user"].keys()) == {
        "id",
        "name",
        "email",
        "is_admin",
        "institution",
        "occupation",
        "education",
        "gender",
        "age",
        "created_at",
    }

    assert file_response.status_code == status.HTTP_200_OK
    assert file_response.json()["file"]["id"] == str(seeded["pdf_file"].id)
    assert {"summary_cards", "timeseries", "top_users", "recent_events", "last_updated_at"}.issubset(file_response.json().keys())

    assert layer_response.status_code == status.HTTP_200_OK
    assert layer_response.json()["layer"]["id"] == str(seeded["layer"].id)
    assert {"summary_cards", "timeseries", "action_breakdown", "recent_events", "last_updated_at"}.issubset(layer_response.json().keys())

    assert event_response.status_code == status.HTTP_200_OK
    assert event_response.json()["operation"]["event_id"] == str(seeded["admin_error"].id)
    assert isinstance(event_response.json()["related_rows"], list)
    assert event_response.json()["related_rows"][0]["event_id"] == str(seeded["admin_related"].id)

    assert endpoint_response.status_code == status.HTTP_200_OK
    assert endpoint_response.json()["endpoint"]["key"] == "file-list"
    assert endpoint_response.json()["endpoint"]["label"] == "/file"


@pytest.mark.anyio
async def test_admin_analytics_export_ready_and_pending(async_client, override_auth, seed_factory):
    seeded = await seed_factory(include_events=True)
    override_auth(user=seeded["admin_user"])

    ready_response = await async_client.post(
        "/admin-analytics/export",
        json={
            "domain": "file-usage",
            "format": "csv",
            "filters": {
                "date_from": "2026-05-01",
                "date_to": "2026-05-31",
                "granularity": "day",
                "category": "Mapa",
            },
            "columns": ["file_name", "downloads", "unique_users"],
        },
    )

    assert ready_response.status_code == status.HTTP_200_OK
    ready_body = ready_response.json()
    assert ready_body["status"] == "ready"
    assert ready_body["name"].endswith(".csv")
    assert ready_body["path"].startswith("/exports/")
    assert ready_body["content_type"] == "text/csv"
    assert ready_body["generated_at"] is not None
    assert ready_body["expires_at"] is not None

    pending_export = models.AdminAnalyticsExport(
        id=uuid4(),
        domain="system-health",
        format="xlsx",
        status="pending",
        name="analytics-system-health-2026-05-14.xlsx",
        path="/exports/analytics-system-health-2026-05-14.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        generated_at=None,
        expires_at=None,
        detail="Exportação em processamento.",
        filters={"endpoint": "file-list"},
        columns=["label", "request_count"],
    )

    async with TesteSessionLocal() as db:
        db.add(pending_export)
        await db.commit()

    pending_response = await async_client.get(f"/admin-analytics/export/{pending_export.id}")

    assert pending_response.status_code == status.HTTP_200_OK
    pending_body = pending_response.json()
    assert pending_body["export_id"] == str(pending_export.id)
    assert pending_body["status"] == "pending"
    assert pending_body["detail"] == "Exportação em processamento."

    async with TesteSessionLocal() as db:
        await db.exec(delete(models.AdminAnalyticsExport).where(models.AdminAnalyticsExport.id.in_([pending_export.id, ready_body["export_id"]])))
        await db.commit()