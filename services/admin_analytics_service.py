from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request

from repositories.admin_analytics_repository import AdminAnalyticsRepository
from sql_app import models
from sql_app.database import SessionLocal


class AdminAnalyticsTracker:
    EXCLUDED_PREFIXES = (
        "/assets/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/favicon.ico",
    )

    def __init__(self, request: Request):
        self.request = request
        self.started_at = perf_counter()
        self.actor_user_id: UUID | None = None
        self.actor_name: str | None = None
        request.state.admin_analytics_tracker = self

    @staticmethod
    async def inject_tracker(request: Request) -> "AdminAnalyticsTracker":
        tracker = getattr(request.state, "admin_analytics_tracker", None)
        if tracker is not None:
            return tracker
        return AdminAnalyticsTracker(request=request)

    def bind_actor(self, user: models.User | models.AnonymousUser | None) -> None:
        if user is None:
            return

        actor_id = getattr(user, "id", None)
        if actor_id is not None:
            self.actor_user_id = actor_id

        actor_name = getattr(user, "user", None)
        if actor_name:
            self.actor_name = actor_name

    async def record(
        self,
        *,
        domain: str,
        event_type: str,
        label: str,
        user: models.User | models.AnonymousUser | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
        status: str | None = None,
        endpoint_key: str | None = None,
        method: str | None = None,
        status_code: int | None = None,
        latency_ms: int | None = None,
        file_id: UUID | str | None = None,
        layer_id: UUID | str | None = None,
        payload: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
    ) -> models.AdminAnalyticsEvent | None:
        if not self.should_track_request():
            return None

        if user is not None:
            self.bind_actor(user)

        resolved_layer_id = layer_id
        if resolved_layer_id is None and target_type == "layer":
            resolved_layer_id = target_id

        async with SessionLocal() as db:
            repository = AdminAnalyticsRepository(db=db)
            return await repository.create_event(
                domain=domain,
                event_type=event_type,
                label=label,
                occurred_at=occurred_at or datetime.utcnow(),
                actor_user_id=self.actor_user_id,
                actor_name=self.actor_name,
                target_type=target_type,
                target_id=target_id,
                status=status,
                endpoint_key=endpoint_key or self.endpoint_key,
                method=method or self.request.method,
                status_code=status_code,
                latency_ms=latency_ms,
                file_id=self._parse_uuid(file_id),
                layer_id=self._parse_uuid(resolved_layer_id),
                payload=payload,
            )

    async def record_system_health(
        self,
        *,
        status_code: int,
        status: str,
        detail: str | None = None,
    ) -> models.AdminAnalyticsEvent | None:
        payload: dict[str, object] = {
            "label": self.route_path,
            "path": self.request.url.path,
            "query": dict(self.request.query_params),
        }
        if detail:
            payload["detail"] = detail

        return await self.record(
            domain="system-health",
            event_type="request",
            label=self.route_path,
            status=status,
            status_code=status_code,
            latency_ms=self.latency_ms,
            payload=payload,
        )

    def build_business_event(
        self,
        *,
        status_code: int,
        status: str,
        detail: str | None = None,
    ) -> dict[str, Any] | None:
        if self.route_path.startswith("/admin-analytics"):
            return None

        payload = self._base_payload(detail=detail)
        method = self.request.method
        path = self.route_path
        path_params = self.request.path_params

        if path == "/token" and method == "POST":
            return self._event(
                domain="user-activity",
                event_type="login",
                label="Login realizado",
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path == "/refresh-token" and method == "POST":
            return self._event(
                domain="user-activity",
                event_type="refresh-token",
                label="Atualizacao de token",
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path == "/check-token" and method == "GET":
            return self._event(
                domain="user-activity",
                event_type="check-token",
                label="Validacao de sessao",
                target_type="user",
                target_id=self._stringify(self.actor_user_id),
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path == "/confirm-email/{temporary_user_id}":
            return self._event(
                domain="user-activity",
                event_type="confirm-email",
                label="Confirmacao de email",
                target_type="temporary-user",
                target_id=self._stringify(path_params.get("temporary_user_id")),
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path == "/users" and method == "POST":
            return self._event(
                domain="user-activity",
                event_type="register",
                label="Cadastro de usuario",
                target_type="user",
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path == "/users" and method == "PUT":
            return self._event(
                domain="user-activity",
                event_type="profile-update",
                label="Atualizacao de perfil",
                target_type="user",
                target_id=self._stringify(self.actor_user_id),
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path == "/recovery-password/{user_email}":
            return self._event(
                domain="user-activity",
                event_type="recovery-password",
                label="Recuperacao de senha",
                target_type="user-email",
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path == "/change-password":
            return self._event(
                domain="user-activity",
                event_type="change-password",
                label="Troca de senha",
                target_type="user",
                target_id=self._stringify(self.actor_user_id),
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path == "/anonymous":
            return self._event(
                domain="user-activity",
                event_type="anonymous-create",
                label="Criacao de usuario anonimo",
                target_type="anonymous-user",
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path in {"/user", "/users", "/user/{id}", "/dashboard/user"} or path.startswith("/group") or path == "/permission":
            return self._build_user_admin_event(status=status, status_code=status_code, payload=payload)

        if path == "/contact":
            return self._event(
                domain="admin-operations",
                event_type="feedback-submit",
                label="Envio de feedback",
                target_type="feedback",
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path.startswith("/file"):
            return self._build_file_event(status=status, status_code=status_code, payload=payload)

        if path.startswith("/process") or path.startswith("/geofiles") or path.startswith("/raster"):
            return self._build_process_event(status=status, status_code=status_code, payload=payload)

        if path.startswith("/layer"):
            return self._build_layer_event(status=status, status_code=status_code, payload=payload)

        if path.startswith("/platform") or path.startswith("/qualified_data") or path.startswith("/time-series") or path.startswith("/wind-rose") or path.startswith("/vertical-profile") or path.startswith("/diurnal-profile"):
            return self._build_platform_event(status=status, status_code=status_code, payload=payload)

        return None

    @property
    def latency_ms(self) -> int:
        return round((perf_counter() - self.started_at) * 1000)

    @property
    def route_path(self) -> str:
        route = self.request.scope.get("route")
        return getattr(route, "path", self.request.url.path)

    @property
    def endpoint_key(self) -> str:
        path = self.route_path.strip("/")
        if not path:
            path = "root"

        segments = []
        for segment in path.split("/"):
            if segment.startswith("{") and segment.endswith("}"):
                segments.append(segment[1:-1])
            else:
                segments.append(segment)
        resource = "-".join(segments)

        if self.request.method == "GET":
            action = "detail" if "{" in self.route_path else "list"
        elif self.request.method == "POST":
            action = "create"
        elif self.request.method == "PUT":
            action = "update"
        elif self.request.method == "DELETE":
            action = "delete"
        else:
            action = self.request.method.lower()

        return f"{resource}-{action}"

    def should_track_request(self) -> bool:
        path = self.request.url.path
        return not any(path.startswith(prefix) for prefix in self.EXCLUDED_PREFIXES)

    def _build_user_admin_event(
        self,
        *,
        status: str,
        status_code: int,
        payload: dict[str, object],
    ) -> dict[str, Any]:
        path = self.route_path
        path_params = self.request.path_params
        if path == "/user" and self.request.method == "GET":
            return self._event(
                domain="user-activity",
                event_type="self-view",
                label="Consulta do proprio usuario",
                target_type="user",
                target_id=self._stringify(self.actor_user_id),
                status=status,
                status_code=status_code,
                payload=payload,
            )

        target_type = "group" if path.startswith("/group") else "permission" if path == "/permission" else "user"
        target_id = self._stringify(path_params.get("id") or path_params.get("group_id") or self.actor_user_id)

        return self._event(
            domain="admin-operations",
            event_type=self._event_type_for_method(default_get="view"),
            label=self._label_for_admin_path(path),
            target_type=target_type,
            target_id=target_id,
            status=status,
            status_code=status_code,
            payload=payload,
        )

    def _build_file_event(
        self,
        *,
        status: str,
        status_code: int,
        payload: dict[str, object],
    ) -> dict[str, Any]:
        file_id = self.request.path_params.get("id")
        if self.request.method == "GET":
            return self._event(
                domain="file-usage",
                event_type="view" if file_id else "list",
                label="Consulta de arquivo" if file_id else "Listagem de arquivos",
                target_type="file",
                target_id=self._stringify(file_id),
                file_id=file_id,
                status=status,
                status_code=status_code,
                payload=payload,
            )

        return self._event(
            domain="admin-operations",
            event_type=self._event_type_for_method(),
            label=self._label_for_admin_path(self.route_path),
            target_type="file",
            target_id=self._stringify(file_id),
            file_id=file_id,
            status=status,
            status_code=status_code,
            payload=payload,
        )

    def _build_process_event(
        self,
        *,
        status: str,
        status_code: int,
        payload: dict[str, object],
    ) -> dict[str, Any]:
        path_params = self.request.path_params
        if self.request.method == "GET" or self.route_path.startswith("/process"):
            return self._event(
                domain="map-usage",
                event_type="view" if self.request.method == "GET" else "run",
                label=self._label_for_map_path(self.route_path),
                target_type="layer" if "table_name" in path_params else "raster" if "raster_name" in path_params else "process",
                target_id=self._stringify(path_params.get("table_name") or path_params.get("raster_name") or path_params.get("energy_type")),
                status=status,
                status_code=status_code,
                payload=payload,
            )

        return self._event(
            domain="admin-operations",
            event_type=self._event_type_for_method(),
            label=self._label_for_admin_path(self.route_path),
            target_type="geofile",
            target_id=self._stringify(path_params.get("table_name") or path_params.get("raster_name")),
            status=status,
            status_code=status_code,
            payload=payload,
        )

    def _build_layer_event(
        self,
        *,
        status: str,
        status_code: int,
        payload: dict[str, object],
    ) -> dict[str, Any]:
        path = self.route_path
        path_params = self.request.path_params
        layer_context = getattr(self.request.state, "layer_event_context", None) or {}
        layer_id = (
            path_params.get("id")
            or path_params.get("layer_id")
            or layer_context.get("layer_id")
        )
        group_id = path_params.get("id") if path.startswith("/layer-group") else None

        if self.request.method == "GET":
            return self._event(
                domain="map-usage",
                event_type="view" if layer_id else "list",
                label=self._label_for_map_path(path),
                target_type="layer" if layer_id else "layer-group",
                target_id=self._stringify(layer_id or group_id),
                layer_id=layer_id,
                status=status,
                status_code=status_code,
                payload=payload,
            )

        if path == "/layer/upload-preview" and self.request.method == "POST":
            upload_details = getattr(self.request.state, "layer_upload_details", None)
            preview_geojson = getattr(self.request.state, "layer_preview_geojson", None)
            preview_payload = {
                **payload,
                "layer_name": layer_context.get("layer_name"),
            }
            if upload_details:
                preview_payload["details"] = upload_details
            if preview_geojson is not None:
                preview_payload["geojson"] = preview_geojson

            return self._event(
                domain="map-usage",
                event_type="upload-preview",
                label="Upload de camada temporaria",
                target_type="uploaded-layer",
                status=status,
                status_code=status_code,
                payload=preview_payload,
            )

        # For layer create/update include GeoJSON summary stored by the endpoint
        if path in {"/layer", "/layer/{id}"} and self.request.method in {"POST", "PUT"}:
            payload = {
                **payload,
                "layer_name": layer_context.get("layer_name"),
                "group_id": layer_context.get("group_id"),
            }
            upload_details = getattr(self.request.state, "layer_upload_details", None)
            if upload_details:
                payload = {**payload, "details": upload_details}

        return self._event(
            domain="admin-operations",
            event_type=self._event_type_for_method(),
            label=self._label_for_admin_path(path),
            target_type="layer-group" if path.startswith("/layer-group") else "layer",
            target_id=self._stringify(group_id or layer_id),
            layer_id=layer_id,
            status=status,
            status_code=status_code,
            payload=payload,
        )

    def _build_platform_event(
        self,
        *,
        status: str,
        status_code: int,
        payload: dict[str, object],
    ) -> dict[str, Any]:
        platform_id = self.request.path_params.get("id")
        if self.request.method == "GET":
            return self._event(
                domain="map-usage",
                event_type="view",
                label=self._label_for_map_path(self.route_path),
                target_type="platform",
                target_id=self._stringify(platform_id),
                status=status,
                status_code=status_code,
                payload=payload,
            )

        return self._event(
            domain="admin-operations",
            event_type=self._event_type_for_method(),
            label=self._label_for_admin_path(self.route_path),
            target_type="platform",
            target_id=self._stringify(platform_id),
            status=status,
            status_code=status_code,
            payload=payload,
        )

    def _base_payload(self, *, detail: str | None) -> dict[str, object]:
        payload: dict[str, object] = {
            "path": self.request.url.path,
            "path_params": dict(self.request.path_params),
            "query": dict(self.request.query_params),
        }
        if detail:
            payload["detail"] = detail
        return payload

    def _event(
        self,
        *,
        domain: str,
        event_type: str,
        label: str,
        target_type: str | None = None,
        target_id: str | None = None,
        file_id: str | UUID | None = None,
        layer_id: str | UUID | None = None,
        status: str,
        status_code: int,
        payload: dict[str, object],
    ) -> dict[str, Any]:
        return {
            "domain": domain,
            "event_type": event_type,
            "label": label,
            "target_type": target_type,
            "target_id": target_id,
            "status": status,
            "status_code": status_code,
            "latency_ms": self.latency_ms,
            "file_id": file_id,
            "layer_id": layer_id,
            "payload": payload,
        }

    def _event_type_for_method(self, default_get: str = "list") -> str:
        if self.request.method == "POST":
            return "create"
        if self.request.method == "PUT":
            return "update"
        if self.request.method == "DELETE":
            return "delete"
        return default_get

    def _label_for_admin_path(self, path: str) -> str:
        if path.startswith("/file"):
            return "Administracao de arquivos"
        if path.startswith("/user") or path.startswith("/users"):
            return "Administracao de usuarios"
        if path.startswith("/group") or path == "/permission":
            return "Administracao de grupos e permissoes"
        if path.startswith("/layer"):
            return "Administracao de camadas"
        if path.startswith("/platform") or path.startswith("/qualified_data"):
            return "Administracao de plataformas"
        if path.startswith("/geofiles") or path.startswith("/raster"):
            return "Administracao de dados geoespaciais"
        return "Operacao administrativa"

    def _label_for_map_path(self, path: str) -> str:
        if path.startswith("/process/geo-processing"):
            return "Processamento geoespacial"
        if path.startswith("/process/raster"):
            return "Consulta de raster"
        if path.startswith("/process/dash-data"):
            return "Consulta de dashboard geoespacial"
        if path.startswith("/geofiles"):
            return "Consulta de camada geoespacial"
        if path.startswith("/layer"):
            return "Consulta de camada"
        if path.startswith("/platform"):
            return "Consulta de plataforma"
        if path.startswith("/time-series"):
            return "Serie temporal de plataforma"
        if path.startswith("/wind-rose"):
            return "Rosa dos ventos"
        if path.startswith("/vertical-profile"):
            return "Perfil vertical"
        if path.startswith("/diurnal-profile"):
            return "Perfil diurno"
        return "Consulta de mapa"

    @staticmethod
    def _stringify(value: Any) -> str | None:
        if value is None or value == "":
            return None
        return str(value)

    @staticmethod
    def _parse_uuid(value: UUID | str | None) -> UUID | None:
        if value is None or value == "":
            return None
        if isinstance(value, UUID):
            return value
        try:
            return UUID(str(value))
        except (TypeError, ValueError):
            return None


AnalyticsTrackerDep = Annotated[AdminAnalyticsTracker, Depends(AdminAnalyticsTracker.inject_tracker)]