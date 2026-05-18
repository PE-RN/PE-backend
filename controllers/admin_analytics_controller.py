from __future__ import annotations

import csv
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta, timezone
from math import ceil
from typing import Annotated, Any, Mapping, Sequence

from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from repositories.admin_analytics_repository import AdminAnalyticsRepository
from schemas.admin_analytics import (
    AdminAnalyticsActivityEvent,
    AdminAnalyticsAdminOperationDetailResponse,
    AdminAnalyticsAdminOperationRow,
    AdminAnalyticsAdminOperationsQuery,
    AdminAnalyticsAdminOperationsResponse,
    AdminAnalyticsAlert,
    AdminAnalyticsBreakdown,
    AdminAnalyticsBreakdownItem,
    AdminAnalyticsEndpointDetail,
    AdminAnalyticsEndpointOption,
    AdminAnalyticsExportRequest,
    AdminAnalyticsExportResponse,
    AdminAnalyticsFileDetail,
    AdminAnalyticsFileUsageDetailResponse,
    AdminAnalyticsFileUsageQuery,
    AdminAnalyticsFileUsageResponse,
    AdminAnalyticsFileUsageRow,
    AdminAnalyticsFilterOptionsQuery,
    AdminAnalyticsFilterOptionsResponse,
    AdminAnalyticsLayerDetail,
    AdminAnalyticsLayerGroupOption,
    AdminAnalyticsLayerOption,
    AdminAnalyticsMapUsageDetailResponse,
    AdminAnalyticsMapUsageQuery,
    AdminAnalyticsMapUsageResponse,
    AdminAnalyticsMapUsageRow,
    AdminAnalyticsOperationDetail,
    AdminAnalyticsOptionItem,
    AdminAnalyticsOverviewQuery,
    AdminAnalyticsOverviewResponse,
    AdminAnalyticsPaginatedFiles,
    AdminAnalyticsPaginatedLayers,
    AdminAnalyticsPaginatedOperations,
    AdminAnalyticsPaginatedSystemHealth,
    AdminAnalyticsPaginatedUsers,
    AdminAnalyticsSummaryCard,
    AdminAnalyticsSystemHealthDetailResponse,
    AdminAnalyticsSystemHealthQuery,
    AdminAnalyticsSystemHealthResponse,
    AdminAnalyticsSystemHealthRow,
    AdminAnalyticsTimeseriesPoint,
    AdminAnalyticsTopUser,
    AdminAnalyticsUserActivityDetailResponse,
    AdminAnalyticsUserActivityQuery,
    AdminAnalyticsUserActivityResponse,
    AdminAnalyticsUserActivityRow,
    AdminAnalyticsUserDetail,
    AdminAnalyticsUserOption,
)
from sql_app import models
from sql_app.database import get_db


class AdminAnalyticsValidationError(Exception):

    def __init__(self, detail: str, errors: list[dict[str, str]]):
        super().__init__(detail)
        self.detail = detail
        self.errors = errors


class AdminAnalyticsController:
    SYSTEM_ENDPOINT_LABELS = {
        "file-list": "/file",
        "file-detail": "/file/{id}",
        "users-list": "/users",
        "layer-list": "/layer-group",
        "layer-create": "/layer",
        "contact": "/contact",
    }
    FILTER_STATUS_CODES = [200, 401, 403, 500]

    def __init__(self, repository: AdminAnalyticsRepository):
        self.repository = repository

    @staticmethod
    async def inject_controller(
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> "AdminAnalyticsController":
        return AdminAnalyticsController(repository=AdminAnalyticsRepository(db=db))

    async def assert_admin(self, user: models.User | models.AnonymousUser) -> None:
        if not isinstance(user, models.User):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão administrativa.")

        persisted_user = await self.repository.get_user_by_id(str(user.id))
        if not persisted_user or not persisted_user.group or persisted_user.group.name != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Não possui permissão administrativa.")

    def parse_query(self, model_class: type[BaseModel], params: Mapping[str, str]) -> BaseModel:
        payload = {key: value for key, value in params.items() if value != ""}
        return self._parse_model(model_class, payload, "Filtros inválidos")

    def parse_body(self, model_class: type[BaseModel], payload: Mapping[str, Any]) -> BaseModel:
        return self._parse_model(model_class, dict(payload), "Payload inválido")

    async def get_filter_options(
        self,
        query: AdminAnalyticsFilterOptionsQuery,
    ) -> AdminAnalyticsFilterOptionsResponse:
        _ = query
        files = await self.repository.list_files()
        layer_groups = await self.repository.list_layer_groups()
        layers = await self.repository.list_layers()
        users = await self.repository.list_users()
        events = await self.repository.list_events()

        endpoint_map = dict(self.SYSTEM_ENDPOINT_LABELS)
        for event in events:
            if event.domain == "system-health" and event.endpoint_key:
                endpoint_map[event.endpoint_key] = self._endpoint_label(event.endpoint_key, event.payload)

        status_codes = sorted(
            {
                *self.FILTER_STATUS_CODES,
                *[event.status_code for event in events if event.domain == "system-health" and event.status_code is not None],
            }
        )

        return AdminAnalyticsFilterOptionsResponse(
            date_presets=["7d", "30d", "90d", "365d"],
            granularities=["hour", "day", "week", "month"],
            file_categories=[
                AdminAnalyticsOptionItem(value=item, label=item)
                for item in sorted({file.category for file in files if file.category})
            ],
            file_subcategories=[
                AdminAnalyticsOptionItem(value=item, label=item)
                for item in sorted({file.sub_category for file in files if file.sub_category})
            ],
            layer_groups=[
                AdminAnalyticsLayerGroupOption(id=str(group.id), name=group.name)
                for group in sorted(layer_groups, key=lambda item: item.name.lower())
            ],
            layers=[
                AdminAnalyticsLayerOption(
                    id=str(layer.id),
                    name=layer.name,
                    group_id=str(layer.layer_group_id) if layer.layer_group_id else None,
                )
                for layer in sorted(layers, key=lambda item: item.name.lower())
            ],
            admin_users=[
                AdminAnalyticsUserOption(id=str(user.id), name=user.user)
                for user in sorted(
                    [user for user in users if self._is_admin_user(user)],
                    key=lambda item: item.user.lower(),
                )
            ],
            system_endpoints=[
                AdminAnalyticsEndpointOption(key=key, label=label)
                for key, label in sorted(endpoint_map.items())
            ],
            status_codes=status_codes,
        )

    async def get_overview(self, query: AdminAnalyticsOverviewQuery) -> AdminAnalyticsOverviewResponse:
        events = await self.repository.list_events()
        current_events = self._filter_events(events, query)
        previous_events = self._filter_events(events, self._previous_period_query(query))

        current_active_users = self._count_active_users(current_events)
        previous_active_users = self._count_active_users(previous_events)
        current_file_events = self._events_for_domain(current_events, "file-usage")
        previous_file_events = self._events_for_domain(previous_events, "file-usage")
        current_map_events = self._events_for_domain(current_events, "map-usage")
        previous_map_events = self._events_for_domain(previous_events, "map-usage")
        current_admin_events = self._events_for_domain(current_events, "admin-operations")
        previous_admin_events = self._events_for_domain(previous_events, "admin-operations")
        current_system_events = self._events_for_domain(current_events, "system-health")
        previous_system_events = self._events_for_domain(previous_events, "system-health")

        users = await self.repository.list_users()
        user_map = self._user_map(users)

        return AdminAnalyticsOverviewResponse(
            summary_cards=[
                self._build_summary_card("active_users", "Usuarios ativos", current_active_users, previous_active_users, query.compare_previous),
                self._build_summary_card("file_usage", "Uso de arquivos", len(current_file_events), len(previous_file_events), query.compare_previous),
                self._build_summary_card("map_usage", "Uso de mapas", len(current_map_events), len(previous_map_events), query.compare_previous),
                self._build_summary_card("admin_operations", "Operacoes administrativas", len(current_admin_events), len(previous_admin_events), query.compare_previous),
                self._build_summary_card("system_health", "Saude do sistema", len(current_system_events), len(previous_system_events), query.compare_previous),
            ],
            tab_counts={
                "user_activity": current_active_users,
                "file_usage": len(current_file_events),
                "map_usage": len(current_map_events),
                "admin_operations": len(current_admin_events),
                "system_health": len(current_system_events),
            },
            timeseries=self._build_timeseries(
                [event.occurred_at for event in current_events],
                query,
                [event.occurred_at for event in previous_events],
            ),
            breakdowns=[
                self._build_breakdown(
                    "domain",
                    "Atividade por modulo",
                    Counter(event.domain for event in current_events),
                ),
                self._build_breakdown(
                    "event_type",
                    "Tipos de eventos",
                    Counter(event.event_type for event in current_events),
                ),
            ],
            alerts=self._build_overview_alerts(current_events),
            recent_activity=self._build_activity_events(current_events, user_map),
            last_updated_at=self._last_updated_at(current_events),
        )

    async def get_user_activity(self, query: AdminAnalyticsUserActivityQuery) -> AdminAnalyticsUserActivityResponse:
        users = await self.repository.list_users()
        events = await self.repository.list_events()

        current_events = self._filter_events(events, query, {"user-activity", "file-usage", "map-usage"})
        previous_events = self._filter_events(events, self._previous_period_query(query), {"user-activity", "file-usage", "map-usage"})
        current_by_user = self._group_events_by_actor(current_events)
        previous_by_user = self._group_events_by_actor(previous_events)

        filtered_users = [
            user for user in users if self._matches_user_filters(user, current_by_user.get(str(user.id), []), query)
        ]
        previous_filtered_users = [
            user for user in users if self._matches_user_filters(user, previous_by_user.get(str(user.id), []), self._previous_period_query(query))
        ]

        rows = [self._build_user_row(user, current_by_user.get(str(user.id), [])) for user in filtered_users]
        paginated = self._paginate_rows(rows, query.page, query.page_size, query.sort_by, query.sort_order)

        return AdminAnalyticsUserActivityResponse(
            summary_cards=[
                self._build_summary_card("users_total", "Usuarios ativos", len(filtered_users), len(previous_filtered_users), query.compare_previous),
                self._build_summary_card(
                    "admin_users",
                    "Usuarios admin",
                    sum(1 for user in filtered_users if self._is_admin_user(user)),
                    sum(1 for user in previous_filtered_users if self._is_admin_user(user)),
                    query.compare_previous,
                ),
                self._build_summary_card(
                    "institutions",
                    "Instituicoes",
                    len({user.institution for user in filtered_users if user.institution}),
                    len({user.institution for user in previous_filtered_users if user.institution}),
                    query.compare_previous,
                ),
            ],
            timeseries=self._build_timeseries(
                [event.occurred_at for user in filtered_users for event in current_by_user.get(str(user.id), [])],
                query,
                [event.occurred_at for user in previous_filtered_users for event in previous_by_user.get(str(user.id), [])],
            ),
            breakdowns=[
                self._build_breakdown("institution", "Instituicoes", Counter(user.institution or "Não informado" for user in filtered_users)),
                self._build_breakdown("occupation", "Ocupacoes", Counter(user.ocupation or "Não informado" for user in filtered_users)),
                self._build_breakdown("education", "Escolaridade", Counter(user.education or "Não informado" for user in filtered_users)),
                self._build_breakdown("gender", "Genero", Counter(user.gender or "Não informado" for user in filtered_users)),
            ],
            table=AdminAnalyticsPaginatedUsers(**paginated),
            last_updated_at=self._last_updated_at(current_events),
        )

    async def get_user_activity_detail(
        self,
        user_id: str,
        query: AdminAnalyticsUserActivityQuery,
    ) -> AdminAnalyticsUserActivityDetailResponse:
        user = await self.repository.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

        events = await self.repository.list_events()
        current_events = self._filter_events(events, query, {"user-activity", "file-usage", "map-usage"})
        user_events = [event for event in current_events if self._uuid_to_str(event.actor_user_id) == str(user.id)]
        if not self._matches_user_filters(user, user_events, query, ignore_user_id=True):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado para os filtros informados.")

        user_row = self._build_user_row(user, user_events)
        detail = AdminAnalyticsUserDetail(
            id=str(user.id),
            name=user.user,
            email=user.email,
            is_admin=self._is_admin_user(user),
            institution=user.institution,
            occupation=user.ocupation,
            education=user.education,
            gender=user.gender,
            age=user.age,
            created_at=self._to_utc(user.created_at),
        )

        return AdminAnalyticsUserActivityDetailResponse(
            user=detail,
            summary_cards=[
                self._build_summary_card("login_count", "Logins", user_row.login_count, None, False),
                self._build_summary_card("downloads_count", "Downloads", user_row.downloads_count, None, False),
                self._build_summary_card("map_actions_count", "Ações em mapa", user_row.map_actions_count, None, False),
            ],
            timeseries=self._build_timeseries([event.occurred_at for event in user_events], query),
            breakdowns=[
                self._build_breakdown("institution", "Instituição", Counter([user.institution or "Não informado"])),
                self._build_breakdown("occupation", "Ocupação", Counter([user.ocupation or "Não informado"])),
                self._build_breakdown("education", "Escolaridade", Counter([user.education or "Não informado"])),
                self._build_breakdown("gender", "Gênero", Counter([user.gender or "Não informado"])),
            ],
            recent_events=self._build_activity_events(user_events, self._user_map([user])),
            last_updated_at=self._last_updated_at(user_events, fallback=user.updated_at),
        )

    async def get_file_usage(self, query: AdminAnalyticsFileUsageQuery) -> AdminAnalyticsFileUsageResponse:
        files = await self.repository.list_files()
        users = await self.repository.list_users()
        events = await self.repository.list_events()

        current_events = self._filter_file_events(events, query)
        previous_query = self._previous_period_query(query)
        previous_events = self._filter_file_events(events, previous_query)
        rows = []
        previous_rows = []

        for file in files:
            if not self._matches_file_filters(file, query):
                continue
            file_events = [event for event in current_events if self._uuid_to_str(event.file_id) == str(file.id)]
            if file_events:
                rows.append(self._build_file_row(file, file_events))

            previous_file_events = [event for event in previous_events if self._uuid_to_str(event.file_id) == str(file.id)]
            if previous_file_events and self._matches_file_filters(file, previous_query):
                previous_rows.append(self._build_file_row(file, previous_file_events))

        paginated = self._paginate_rows(rows, query.page, query.page_size, query.sort_by, query.sort_order)
        return AdminAnalyticsFileUsageResponse(
            summary_cards=[
                self._build_summary_card("files_total", "Arquivos", len(rows), len(previous_rows), query.compare_previous),
                self._build_summary_card(
                    "downloads_total",
                    "Downloads totais",
                    len(current_events),
                    len(previous_events),
                    query.compare_previous,
                ),
                self._build_summary_card(
                    "unique_users",
                    "Usuarios unicos",
                    len({self._uuid_to_str(event.actor_user_id) for event in current_events if event.actor_user_id}),
                    len({self._uuid_to_str(event.actor_user_id) for event in previous_events if event.actor_user_id}),
                    query.compare_previous,
                ),
            ],
            timeseries=self._build_timeseries(
                [event.occurred_at for event in current_events],
                query,
                [event.occurred_at for event in previous_events],
            ),
            breakdowns=[
                self._build_breakdown("category", "Categorias", Counter(row.category or "Não informado" for row in rows)),
                self._build_breakdown("sub_category", "Subcategorias", Counter(row.sub_category or "Não informado" for row in rows)),
                self._build_breakdown("action", "Ações", Counter(event.event_type for event in current_events)),
            ],
            table=AdminAnalyticsPaginatedFiles(**paginated),
            last_updated_at=self._last_updated_at(current_events),
        )

    async def get_file_usage_detail(
        self,
        file_id: str,
        query: AdminAnalyticsFileUsageQuery,
    ) -> AdminAnalyticsFileUsageDetailResponse:
        file = await self.repository.get_file_by_id(file_id)
        if not file:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado.")

        if not self._matches_file_filters(file, query, ignore_file_id=True):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado para os filtros informados.")

        events = await self.repository.list_events()
        users = await self.repository.list_users()
        user_map = self._user_map(users)
        file_events = [
            event for event in self._filter_file_events(events, query)
            if self._uuid_to_str(event.file_id) == str(file.id)
        ]

        top_users_counter = Counter(self._uuid_to_str(event.actor_user_id) for event in file_events if event.actor_user_id)
        top_users = []
        for user_id, value in top_users_counter.most_common(5):
            user = user_map.get(user_id)
            if not user:
                continue
            top_users.append(
                AdminAnalyticsTopUser(
                    user_id=user_id,
                    user_name=user.user,
                    email=user.email,
                    value=value,
                    formatted_value=self._format_number(value),
                )
            )

        return AdminAnalyticsFileUsageDetailResponse(
            file=AdminAnalyticsFileDetail(
                id=str(file.id),
                name=file.name,
                path=file.path,
                category=file.category,
                sub_category=file.sub_category,
                created_at=self._to_utc(file.created_at),
            ),
            summary_cards=[
                self._build_summary_card("downloads_total", "Downloads totais", len(file_events), None, False),
                self._build_summary_card(
                    "unique_users",
                    "Usuarios unicos",
                    len({self._uuid_to_str(event.actor_user_id) for event in file_events if event.actor_user_id}),
                    None,
                    False,
                ),
                self._build_summary_card("events_total", "Eventos", len(file_events), None, False),
            ],
            timeseries=self._build_timeseries([event.occurred_at for event in file_events], query),
            top_users=top_users,
            recent_events=self._build_activity_events(file_events, user_map),
            last_updated_at=self._last_updated_at(file_events, fallback=file.updated_at),
        )

    async def get_map_usage(self, query: AdminAnalyticsMapUsageQuery) -> AdminAnalyticsMapUsageResponse:
        layers = await self.repository.list_layers()
        layer_groups = await self.repository.list_layer_groups()
        events = await self.repository.list_events()

        current_events = self._filter_map_events(events, query)
        previous_query = self._previous_period_query(query)
        previous_events = self._filter_map_events(events, previous_query)
        group_map = self._layer_group_map(layer_groups)

        rows = []
        previous_rows = []
        for layer in layers:
            if not self._matches_layer_filters(layer, group_map, query):
                continue
            layer_events = [event for event in current_events if self._uuid_to_str(event.layer_id) == str(layer.id)]
            if layer_events:
                rows.append(self._build_layer_row(layer, group_map, layer_events))

            previous_layer_events = [event for event in previous_events if self._uuid_to_str(event.layer_id) == str(layer.id)]
            if previous_layer_events and self._matches_layer_filters(layer, group_map, previous_query):
                previous_rows.append(self._build_layer_row(layer, group_map, previous_layer_events))

        paginated = self._paginate_rows(rows, query.page, query.page_size, query.sort_by, query.sort_order)
        return AdminAnalyticsMapUsageResponse(
            summary_cards=[
                self._build_summary_card("layers_total", "Camadas", len(rows), len(previous_rows), query.compare_previous),
                self._build_summary_card("views_total", "Visualizações", len(current_events), len(previous_events), query.compare_previous),
                self._build_summary_card(
                    "unique_users",
                    "Usuários únicos",
                    len({self._uuid_to_str(event.actor_user_id) for event in current_events if event.actor_user_id}),
                    len({self._uuid_to_str(event.actor_user_id) for event in previous_events if event.actor_user_id}),
                    query.compare_previous,
                ),
            ],
            timeseries=self._build_timeseries(
                [event.occurred_at for event in current_events],
                query,
                [event.occurred_at for event in previous_events],
            ),
            breakdowns=[
                self._build_breakdown("layer_group", "Grupos de camadas", Counter(row.group_name or "Sem grupo" for row in rows)),
                self._build_breakdown("action", "Ações", Counter(event.event_type for event in current_events)),
                self._build_breakdown(
                    "theme",
                    "Temas",
                    Counter((event.payload or {}).get("theme") or "Não informado" for event in current_events),
                ),
            ],
            table=AdminAnalyticsPaginatedLayers(**paginated),
            last_updated_at=self._last_updated_at(current_events),
        )

    async def get_map_usage_detail(
        self,
        layer_id: str,
        query: AdminAnalyticsMapUsageQuery,
    ) -> AdminAnalyticsMapUsageDetailResponse:
        layer = await self.repository.get_layer_by_id(layer_id)
        if not layer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camada não encontrada.")

        layer_groups = await self.repository.list_layer_groups()
        group_map = self._layer_group_map(layer_groups)
        if not self._matches_layer_filters(layer, group_map, query, ignore_layer_id=True):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camada não encontrada para os filtros informados.")

        events = await self.repository.list_events()
        users = await self.repository.list_users()
        user_map = self._user_map(users)
        layer_events = [
            event for event in self._filter_map_events(events, query)
            if self._uuid_to_str(event.layer_id) == str(layer.id)
        ]

        return AdminAnalyticsMapUsageDetailResponse(
            layer=AdminAnalyticsLayerDetail(
                id=str(layer.id),
                name=layer.name,
                subtitle=layer.subtitle,
                path=layer.path,
                path_icon=layer.path_icon,
                group_id=str(layer.layer_group_id) if layer.layer_group_id else None,
                group_name=group_map.get(str(layer.layer_group_id)).name if layer.layer_group_id and group_map.get(str(layer.layer_group_id)) else None,
                activated=layer.activated,
                created_at=self._to_utc(layer.created_at),
            ),
            summary_cards=[
                self._build_summary_card("views_total", "Visualizações", len(layer_events), None, False),
                self._build_summary_card(
                    "unique_users",
                    "Usuários únicos",
                    len({self._uuid_to_str(event.actor_user_id) for event in layer_events if event.actor_user_id}),
                    None,
                    False,
                ),
                self._build_summary_card("activated", "Ativada", 1 if layer.activated else 0, None, False),
            ],
            timeseries=self._build_timeseries([event.occurred_at for event in layer_events], query),
            action_breakdown=self._build_breakdown_items(Counter(event.event_type for event in layer_events)),
            recent_events=self._build_activity_events(layer_events, user_map),
            last_updated_at=self._last_updated_at(layer_events, fallback=layer.updated_at),
        )

    async def get_admin_operations(self, query: AdminAnalyticsAdminOperationsQuery) -> AdminAnalyticsAdminOperationsResponse:
        events = await self.repository.list_events()
        users = await self.repository.list_users()
        user_map = self._user_map(users)

        current_events = self._filter_admin_operation_events(events, query)
        previous_query = self._previous_period_query(query)
        previous_events = self._filter_admin_operation_events(events, previous_query)
        rows = [self._build_admin_operation_row(event, user_map) for event in current_events]
        previous_rows = [self._build_admin_operation_row(event, user_map) for event in previous_events]
        paginated = self._paginate_rows(rows, query.page, query.page_size, query.sort_by, query.sort_order)

        return AdminAnalyticsAdminOperationsResponse(
            summary_cards=[
                self._build_summary_card("operations_total", "Operações", len(rows), len(previous_rows), query.compare_previous),
                self._build_summary_card(
                    "failed_operations",
                    "Falhas",
                    sum(1 for row in rows if row.status.lower() == "error"),
                    sum(1 for row in previous_rows if row.status.lower() == "error"),
                    query.compare_previous,
                ),
                self._build_summary_card(
                    "admin_users",
                    "Admins atuando",
                    len({row.admin_user_id for row in rows if row.admin_user_id}),
                    len({row.admin_user_id for row in previous_rows if row.admin_user_id}),
                    query.compare_previous,
                ),
            ],
            timeseries=self._build_timeseries(
                [event.occurred_at for event in current_events],
                query,
                [event.occurred_at for event in previous_events],
            ),
            breakdowns=[
                self._build_breakdown("action", "Ações", Counter(row.action for row in rows)),
                self._build_breakdown("target_type", "Tipos de alvo", Counter(row.target_type for row in rows)),
                self._build_breakdown("status", "Status", Counter(row.status for row in rows)),
            ],
            table=AdminAnalyticsPaginatedOperations(**paginated),
            last_updated_at=self._last_updated_at(current_events),
        )

    async def get_admin_operation_detail(
        self,
        event_id: str,
        query: AdminAnalyticsAdminOperationsQuery,
    ) -> AdminAnalyticsAdminOperationDetailResponse:
        event = await self.repository.get_event_by_id(event_id)
        if not event or event.domain != "admin-operations":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operação administrativa não encontrada.")

        if not self._matches_admin_operation_filters(event, query):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operação administrativa não encontrada para os filtros informados.")

        events = await self.repository.list_events()
        users = await self.repository.list_users()
        user_map = self._user_map(users)
        related_events = [
            row for row in self._filter_admin_operation_events(events, query)
            if row.target_id == event.target_id and row.target_type == event.target_type and row.id != event.id
        ]

        operation = self._build_admin_operation_detail(event, user_map)
        return AdminAnalyticsAdminOperationDetailResponse(
            operation=operation,
            related_rows=[self._build_admin_operation_row(row, user_map) for row in related_events],
            last_updated_at=self._last_updated_at([event, *related_events], fallback=event.updated_at),
        )

    async def get_system_health(self, query: AdminAnalyticsSystemHealthQuery) -> AdminAnalyticsSystemHealthResponse:
        events = await self.repository.list_events()
        current_events = self._filter_system_health_events(events, query)
        previous_events = self._filter_system_health_events(events, self._previous_period_query(query))

        rows = [self._build_system_health_row(endpoint_key, method, grouped_events) for (endpoint_key, method), grouped_events in self._group_system_events(current_events).items()]
        previous_rows = [self._build_system_health_row(endpoint_key, method, grouped_events) for (endpoint_key, method), grouped_events in self._group_system_events(previous_events).items()]
        paginated = self._paginate_rows(rows, query.page, query.page_size, query.sort_by, query.sort_order)

        return AdminAnalyticsSystemHealthResponse(
            summary_cards=[
                self._build_summary_card("request_count", "Requisicoes", len(current_events), len(previous_events), query.compare_previous),
                self._build_summary_card(
                    "error_count",
                    "Erros",
                    sum(1 for event in current_events if (event.status_code or 0) >= 400),
                    sum(1 for event in previous_events if (event.status_code or 0) >= 400),
                    query.compare_previous,
                ),
                self._build_summary_card(
                    "avg_latency_ms",
                    "Latencia media",
                    self._average_latency(current_events),
                    self._average_latency(previous_events),
                    query.compare_previous,
                ),
            ],
            timeseries=self._build_timeseries(
                [event.occurred_at for event in current_events],
                query,
                [event.occurred_at for event in previous_events],
            ),
            status_breakdown=self._build_breakdown_items(
                Counter(str(event.status_code or 0) for event in current_events)
            ),
            latency_buckets=self._build_latency_buckets(current_events),
            table=AdminAnalyticsPaginatedSystemHealth(**paginated),
            last_updated_at=self._last_updated_at(current_events),
        )

    async def get_system_health_detail(
        self,
        endpoint_key: str,
        query: AdminAnalyticsSystemHealthQuery,
    ) -> AdminAnalyticsSystemHealthDetailResponse:
        events = await self.repository.list_events()
        endpoint_events = [
            event for event in self._filter_system_health_events(events, query)
            if event.endpoint_key == endpoint_key
        ]
        if not endpoint_events:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint não encontrado.")

        method = query.method or endpoint_events[0].method or "GET"
        return AdminAnalyticsSystemHealthDetailResponse(
            endpoint=AdminAnalyticsEndpointDetail(
                key=endpoint_key,
                label=self._endpoint_label(endpoint_key, endpoint_events[0].payload),
                method=method,
            ),
            summary_cards=[
                self._build_summary_card("request_count", "Requisicoes", len(endpoint_events), None, False),
                self._build_summary_card(
                    "error_count",
                    "Erros",
                    sum(1 for event in endpoint_events if (event.status_code or 0) >= 400),
                    None,
                    False,
                ),
                self._build_summary_card(
                    "avg_latency_ms",
                    "Latencia media",
                    self._average_latency(endpoint_events),
                    None,
                    False,
                ),
            ],
            timeseries=self._build_timeseries([event.occurred_at for event in endpoint_events], query),
            status_breakdown=self._build_breakdown_items(Counter(str(event.status_code or 0) for event in endpoint_events)),
            recent_errors=self._build_activity_events(
                [event for event in endpoint_events if (event.status_code or 0) >= 400],
                {},
            ),
            last_updated_at=self._last_updated_at(endpoint_events),
        )

    async def generate_export_file(self, export_request: AdminAnalyticsExportRequest):
        from fastapi.responses import StreamingResponse
        import openpyxl

        domain = export_request.domain
        # Build the query for the target domain, forcing full-page fetch (no pagination)
        base_filters = {**export_request.filters, "page": 1, "page_size": 10_000, "compare_previous": False}

        _DOMAIN_MAP: dict[str, tuple[type[BaseModel], Any]] = {
            "user-activity": (AdminAnalyticsUserActivityQuery, self.get_user_activity),
            "file-usage": (AdminAnalyticsFileUsageQuery, self.get_file_usage),
            "map-usage": (AdminAnalyticsMapUsageQuery, self.get_map_usage),
            "admin-operations": (AdminAnalyticsAdminOperationsQuery, self.get_admin_operations),
            "system-health": (AdminAnalyticsSystemHealthQuery, self.get_system_health),
            "overview": (AdminAnalyticsOverviewQuery, None),
        }

        if domain not in _DOMAIN_MAP:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Domínio inválido: {domain}")

        query_class, method = _DOMAIN_MAP[domain]
        try:
            query = query_class.model_validate(base_filters)
        except Exception:
            query = query_class()

        # Fetch rows
        if domain == "overview":
            response_data = await self.get_overview(query)
            rows = [event.model_dump() for event in response_data.recent_activity]
        else:
            response_data = await method(query)
            rows = [row.model_dump() for row in response_data.table.rows]

        # Apply column filter if the caller specified columns
        allowed = set(export_request.columns) if export_request.columns else None
        if allowed and rows:
            rows = [{k: v for k, v in row.items() if k in allowed} for row in rows]

        # Ensure there is always at least an empty header row
        if not rows:
            rows = [{}]

        export_name = f"analytics-{domain}-{datetime.utcnow().date().isoformat()}.{export_request.format}"

        def _cell(value: Any) -> str:
            if value is None:
                return ""
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value)

        if export_request.format == "csv":
            fieldnames = list(rows[0].keys())
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows({k: _cell(v) for k, v in row.items()} for row in rows)
            content = buf.getvalue().encode("utf-8-sig")  # BOM so Excel opens correctly
            return StreamingResponse(
                io.BytesIO(content),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{export_name}"'},
            )

        if export_request.format == "xlsx":
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = domain[:31]  # sheet name max 31 chars
            cols = list(rows[0].keys())
            ws.append(cols)
            for row in rows:
                ws.append([_cell(row.get(col)) for col in cols])
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            return StreamingResponse(
                buf,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{export_name}"'},
            )

        if export_request.format == "json":
            serialized = [{k: _cell(v) for k, v in row.items()} for row in rows]
            content = json.dumps(serialized, ensure_ascii=False).encode("utf-8")
            return StreamingResponse(
                io.BytesIO(content),
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{export_name}"'},
            )

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Formato não suportado: {export_request.format}")

    async def get_export(self, export_id: str) -> AdminAnalyticsExportResponse:
        export = await self.repository.get_export_by_id(export_id)
        if not export:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exportação não encontrada.")
        return self._build_export_response(export)

    def _parse_model(self, model_class: type[BaseModel], payload: Mapping[str, Any], detail: str) -> BaseModel:
        try:
            return model_class.model_validate(payload)
        except ValidationError as exc:
            errors = []
            for item in exc.errors():
                location = [str(value) for value in item.get("loc", []) if value != "__root__"]
                errors.append(
                    {
                        "field": location[0] if location else "non_field_error",
                        "message": item.get("msg", "Valor inválido"),
                    }
                )
            raise AdminAnalyticsValidationError(detail=detail, errors=errors) from exc

    def _filter_events(
        self,
        events: Sequence[models.AdminAnalyticsEvent],
        query: BaseModel,
        domains: set[str] | None = None,
    ) -> list[models.AdminAnalyticsEvent]:
        filtered = []
        start_at, end_at = self._period_bounds(query)
        search = self._normalized(getattr(query, "search", ""))

        for event in events:
            occurred_at = self._as_naive(event.occurred_at)
            if domains and event.domain not in domains:
                continue
            if occurred_at < start_at or occurred_at > end_at:
                continue
            if search and not self._matches_search(
                search,
                event.label,
                event.actor_name,
                event.target_type,
                event.target_id,
                event.endpoint_key,
                json.dumps(event.payload or {}, ensure_ascii=False),
            ):
                continue
            filtered.append(event)
        return filtered

    def _filter_file_events(
        self,
        events: Sequence[models.AdminAnalyticsEvent],
        query: AdminAnalyticsFileUsageQuery,
    ) -> list[models.AdminAnalyticsEvent]:
        filtered = []
        for event in self._filter_events(events, query, {"file-usage"}):
            if query.user_id and self._uuid_to_str(event.actor_user_id) != query.user_id:
                continue
            if query.action and self._normalized(event.event_type) != self._normalized(query.action):
                continue
            if query.file_id and self._uuid_to_str(event.file_id) != query.file_id:
                continue
            filtered.append(event)
        return filtered

    def _filter_map_events(
        self,
        events: Sequence[models.AdminAnalyticsEvent],
        query: AdminAnalyticsMapUsageQuery,
    ) -> list[models.AdminAnalyticsEvent]:
        filtered = []
        for event in self._filter_events(events, query, {"map-usage"}):
            payload = event.payload or {}
            if query.layer_id and self._uuid_to_str(event.layer_id) != query.layer_id:
                continue
            if query.action and self._normalized(event.event_type) != self._normalized(query.action):
                continue
            if query.theme and self._normalized(payload.get("theme")) != self._normalized(query.theme):
                continue
            if query.raster_name and self._normalized(payload.get("raster_name")) != self._normalized(query.raster_name):
                continue
            if query.search_term and not self._matches_search(self._normalized(query.search_term), payload.get("search_term")):
                continue
            filtered.append(event)
        return filtered

    def _filter_admin_operation_events(
        self,
        events: Sequence[models.AdminAnalyticsEvent],
        query: AdminAnalyticsAdminOperationsQuery,
    ) -> list[models.AdminAnalyticsEvent]:
        return [event for event in self._filter_events(events, query, {"admin-operations"}) if self._matches_admin_operation_filters(event, query)]

    def _filter_system_health_events(
        self,
        events: Sequence[models.AdminAnalyticsEvent],
        query: AdminAnalyticsSystemHealthQuery,
    ) -> list[models.AdminAnalyticsEvent]:
        filtered = []
        for event in self._filter_events(events, query, {"system-health"}):
            if query.endpoint and event.endpoint_key != query.endpoint:
                continue
            if query.method and self._normalized(event.method) != self._normalized(query.method):
                continue
            if query.status_code is not None and event.status_code != query.status_code:
                continue
            if query.min_latency_ms is not None and (event.latency_ms or 0) < query.min_latency_ms:
                continue
            if query.max_latency_ms is not None and (event.latency_ms or 0) > query.max_latency_ms:
                continue
            filtered.append(event)
        return filtered

    def _matches_user_filters(
        self,
        user: models.User,
        user_events: Sequence[models.AdminAnalyticsEvent],
        query: AdminAnalyticsUserActivityQuery,
        ignore_user_id: bool = False,
    ) -> bool:
        if not user_events:
            return False
        if not ignore_user_id and query.user_id and str(user.id) != query.user_id:
            return False
        if query.institution and self._normalized(user.institution) != self._normalized(query.institution):
            return False
        if query.occupation and self._normalized(user.ocupation) != self._normalized(query.occupation):
            return False
        if query.education and self._normalized(user.education) != self._normalized(query.education):
            return False
        if query.gender and self._normalized(user.gender) != self._normalized(query.gender):
            return False
        if query.is_admin is not None and self._is_admin_user(user) != query.is_admin:
            return False
        if query.event_type and not any(self._normalized(event.event_type) == self._normalized(query.event_type) for event in user_events):
            return False
        age_value = self._parse_int(user.age)
        if query.age_min is not None and (age_value is None or age_value < query.age_min):
            return False
        if query.age_max is not None and (age_value is None or age_value > query.age_max):
            return False
        if query.search and not self._matches_search(
            self._normalized(query.search),
            user.user,
            user.email,
            user.institution,
            user.ocupation,
            user.education,
            user.gender,
        ):
            return False
        return True

    def _matches_file_filters(
        self,
        file: models.PdfFile,
        query: AdminAnalyticsFileUsageQuery,
        ignore_file_id: bool = False,
    ) -> bool:
        if not ignore_file_id and query.file_id and str(file.id) != query.file_id:
            return False
        if query.category and self._normalized(file.category) != self._normalized(query.category):
            return False
        if query.sub_category and self._normalized(file.sub_category) != self._normalized(query.sub_category):
            return False
        if query.search and not self._matches_search(self._normalized(query.search), file.name, file.category, file.sub_category):
            return False
        return True

    def _matches_layer_filters(
        self,
        layer: models.Layer,
        group_map: dict[str, models.LayerGroups],
        query: AdminAnalyticsMapUsageQuery,
        ignore_layer_id: bool = False,
    ) -> bool:
        if not ignore_layer_id and query.layer_id and str(layer.id) != query.layer_id:
            return False
        if query.layer_group_id and self._uuid_to_str(layer.layer_group_id) != query.layer_group_id:
            return False
        if query.search and not self._matches_search(self._normalized(query.search), layer.name, layer.subtitle, group_map.get(self._uuid_to_str(layer.layer_group_id), None).name if self._uuid_to_str(layer.layer_group_id) in group_map else None):
            return False
        return True

    def _matches_admin_operation_filters(
        self,
        event: models.AdminAnalyticsEvent,
        query: AdminAnalyticsAdminOperationsQuery,
    ) -> bool:
        if query.admin_user_id and self._uuid_to_str(event.actor_user_id) != query.admin_user_id:
            return False
        if query.action and self._normalized(event.event_type) != self._normalized(query.action):
            return False
        if query.target_type and self._normalized(event.target_type) != self._normalized(query.target_type):
            return False
        if query.target_id and self._normalized(event.target_id) != self._normalized(query.target_id):
            return False
        if query.status and self._normalized(event.status) != self._normalized(query.status):
            return False
        if query.search and not self._matches_search(
            self._normalized(query.search),
            event.label,
            (event.payload or {}).get("target_label"),
            (event.payload or {}).get("detail"),
        ):
            return False
        return True

    def _build_user_row(
        self,
        user: models.User,
        user_events: Sequence[models.AdminAnalyticsEvent],
    ) -> AdminAnalyticsUserActivityRow:
        login_events = [event for event in user_events if event.domain == "user-activity" and self._normalized(event.event_type) == "login"]
        file_events = [event for event in user_events if event.domain == "file-usage"]
        map_events = [event for event in user_events if event.domain == "map-usage"]
        last_login = max((event.occurred_at for event in login_events), default=None)
        return AdminAnalyticsUserActivityRow(
            user_id=str(user.id),
            user_name=user.user,
            email=user.email,
            is_admin=self._is_admin_user(user),
            institution=user.institution,
            last_login_at=self._to_utc(last_login) if last_login else None,
            login_count=len(login_events),
            active_days=len({self._as_naive(event.occurred_at).date() for event in user_events}),
            downloads_count=len(file_events),
            map_actions_count=len(map_events),
        )

    def _build_file_row(
        self,
        file: models.PdfFile,
        file_events: Sequence[models.AdminAnalyticsEvent],
    ) -> AdminAnalyticsFileUsageRow:
        last_download = max((event.occurred_at for event in file_events), default=None)
        return AdminAnalyticsFileUsageRow(
            file_id=str(file.id),
            file_name=file.name,
            category=file.category,
            sub_category=file.sub_category,
            created_at=self._to_utc(file.created_at),
            downloads=len(file_events),
            unique_users=len({self._uuid_to_str(event.actor_user_id) for event in file_events if event.actor_user_id}),
            last_download_at=self._to_utc(last_download) if last_download else None,
        )

    def _build_layer_row(
        self,
        layer: models.Layer,
        group_map: dict[str, models.LayerGroups],
        layer_events: Sequence[models.AdminAnalyticsEvent],
    ) -> AdminAnalyticsMapUsageRow:
        group_id = self._uuid_to_str(layer.layer_group_id)
        group = group_map.get(group_id)
        last_viewed = max((event.occurred_at for event in layer_events), default=None)
        return AdminAnalyticsMapUsageRow(
            layer_id=str(layer.id),
            layer_name=layer.name,
            group_id=group_id,
            group_name=group.name if group else None,
            activated=layer.activated,
            created_at=self._to_utc(layer.created_at),
            views=len(layer_events),
            unique_users=len({self._uuid_to_str(event.actor_user_id) for event in layer_events if event.actor_user_id}),
            last_viewed_at=self._to_utc(last_viewed) if last_viewed else None,
        )

    def _build_admin_operation_row(
        self,
        event: models.AdminAnalyticsEvent,
        user_map: dict[str, models.User],
    ) -> AdminAnalyticsAdminOperationRow:
        actor_id = self._uuid_to_str(event.actor_user_id)
        actor = user_map.get(actor_id) if actor_id else None
        return AdminAnalyticsAdminOperationRow(
            event_id=str(event.id),
            action=event.event_type,
            target_type=event.target_type or "",
            target_id=event.target_id or "",
            target_label=(event.payload or {}).get("target_label") or event.label,
            admin_user_id=actor_id,
            admin_user_name=actor.user if actor else event.actor_name,
            status=event.status or "success",
            occurred_at=self._to_utc(event.occurred_at),
            detail=(event.payload or {}).get("detail"),
        )

    def _build_admin_operation_detail(
        self,
        event: models.AdminAnalyticsEvent,
        user_map: dict[str, models.User],
    ) -> AdminAnalyticsOperationDetail:
        row = self._build_admin_operation_row(event, user_map)
        return AdminAnalyticsOperationDetail(**row.model_dump())

    def _build_system_health_row(
        self,
        endpoint_key: str,
        method: str,
        events: Sequence[models.AdminAnalyticsEvent],
    ) -> AdminAnalyticsSystemHealthRow:
        status_code = max((event.status_code or 0 for event in events), default=0)
        last_seen = max((event.occurred_at for event in events), default=None)
        return AdminAnalyticsSystemHealthRow(
            endpoint_key=endpoint_key,
            label=self._endpoint_label(endpoint_key, events[0].payload if events else None),
            method=method,
            status_code=status_code,
            request_count=len(events),
            error_count=sum(1 for event in events if (event.status_code or 0) >= 400),
            avg_latency_ms=self._average_latency(events),
            p95_latency_ms=self._p95_latency(events),
            last_seen_at=self._to_utc(last_seen) if last_seen else None,
        )

    def _build_overview_alerts(self, events: Sequence[models.AdminAnalyticsEvent]) -> list[AdminAnalyticsAlert]:
        alerts = []
        system_errors = [event for event in events if event.domain == "system-health" and (event.status_code or 0) >= 500]
        if system_errors:
            endpoint_label = self._endpoint_label(system_errors[0].endpoint_key or "system-health", system_errors[0].payload)
            alerts.append(
                AdminAnalyticsAlert(
                    key="error-spike",
                    level="warning",
                    label="Aumento de erros 500",
                    detail=f"O endpoint {endpoint_label} apresentou crescimento de falhas no período analisado.",
                )
            )

        failed_admin_ops = [event for event in events if event.domain == "admin-operations" and self._normalized(event.status) == "error"]
        if failed_admin_ops:
            alerts.append(
                AdminAnalyticsAlert(
                    key="admin-operation-errors",
                    level="critical",
                    label="Falhas em operações administrativas",
                    detail="Há operações administrativas com status de erro no período analisado.",
                )
            )
        return alerts

    def _build_activity_events(
        self,
        events: Sequence[models.AdminAnalyticsEvent],
        user_map: dict[str, models.User],
        limit: int = 10,
    ) -> list[AdminAnalyticsActivityEvent]:
        sorted_events = sorted(events, key=lambda item: self._as_naive(item.occurred_at), reverse=True)[:limit]
        return [
            AdminAnalyticsActivityEvent(
                id=str(event.id),
                domain=event.domain,
                label=event.label,
                actor_name=self._actor_name(event, user_map),
                occurred_at=self._to_utc(event.occurred_at),
                metadata_summary=self._metadata_summary(event),
            )
            for event in sorted_events
        ]

    def _build_timeseries(
        self,
        current_datetimes: Sequence[datetime],
        query: BaseModel,
        previous_datetimes: Sequence[datetime] | None = None,
    ) -> list[AdminAnalyticsTimeseriesPoint]:
        current_counter: Counter[str] = Counter()
        previous_counter: Counter[str] = Counter()
        labels: dict[str, str] = {}

        for occurred_at in current_datetimes:
            bucket, label = self._bucket_for(self._as_naive(occurred_at), getattr(query, "granularity", "day"))
            current_counter[bucket] += 1
            labels[bucket] = label

        if previous_datetimes:
            shift_days = (getattr(query, "date_to") - getattr(query, "date_from")).days + 1
            for occurred_at in previous_datetimes:
                shifted = self._as_naive(occurred_at) + timedelta(days=shift_days)
                bucket, label = self._bucket_for(shifted, getattr(query, "granularity", "day"))
                previous_counter[bucket] += 1
                labels.setdefault(bucket, label)

        buckets = sorted({*current_counter.keys(), *previous_counter.keys()})
        return [
            AdminAnalyticsTimeseriesPoint(
                bucket=bucket,
                label=labels[bucket],
                value=current_counter.get(bucket, 0),
                compare_value=previous_counter.get(bucket, 0) if getattr(query, "compare_previous", False) else None,
            )
            for bucket in buckets
        ]

    def _build_breakdown(self, key: str, label: str, counter: Counter[str]) -> AdminAnalyticsBreakdown:
        return AdminAnalyticsBreakdown(
            key=key,
            label=label,
            items=self._build_breakdown_items(counter),
        )

    def _build_breakdown_items(self, counter: Counter[str]) -> list[AdminAnalyticsBreakdownItem]:
        total = sum(counter.values())
        items = []
        for item_key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0])):
            items.append(
                AdminAnalyticsBreakdownItem(
                    key=str(item_key),
                    label=str(item_key),
                    value=value,
                    formatted_value=self._format_number(value),
                    share=round((value / total) if total else 0, 4),
                )
            )
        return items

    def _build_latency_buckets(self, events: Sequence[models.AdminAnalyticsEvent]) -> list[AdminAnalyticsBreakdownItem]:
        counter = Counter()
        for event in events:
            latency = event.latency_ms or 0
            if latency < 100:
                counter["<100ms"] += 1
            elif latency < 300:
                counter["100-299ms"] += 1
            elif latency < 1000:
                counter["300-999ms"] += 1
            else:
                counter["1000ms+"] += 1
        return self._build_breakdown_items(counter)

    def _build_summary_card(
        self,
        key: str,
        label: str,
        current_value: int | float,
        previous_value: int | float | None,
        compare_previous: bool,
    ) -> AdminAnalyticsSummaryCard:
        delta_value = None
        delta_label = None
        trend = None
        if compare_previous and previous_value is not None:
            if previous_value == 0:
                delta_value = 0 if current_value == 0 else 100
            else:
                delta_value = round(((current_value - previous_value) / previous_value) * 100)
            trend = "up" if delta_value > 0 else "down" if delta_value < 0 else "flat"
            signal = "+" if delta_value > 0 else ""
            delta_label = f"{signal}{delta_value}% vs. periodo anterior"

        return AdminAnalyticsSummaryCard(
            key=key,
            label=label,
            value=current_value,
            formatted_value=self._format_number(current_value),
            delta_value=delta_value,
            delta_label=delta_label,
            trend=trend,
        )

    def _paginate_rows(
        self,
        rows: Sequence[BaseModel],
        page: int,
        page_size: int,
        sort_by: str,
        sort_order: str,
    ) -> dict[str, Any]:
        materialized_rows = list(rows)
        if sort_by:
            materialized_rows.sort(
                key=lambda row: self._sort_value(getattr(row, sort_by, None)),
                reverse=sort_order == "desc",
            )

        total_rows = len(materialized_rows)
        total_pages = ceil(total_rows / page_size) if total_rows else 0
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        return {
            "page": page,
            "page_size": page_size,
            "total_rows": total_rows,
            "total_pages": total_pages,
            "rows": materialized_rows[start_index:end_index],
        }

    def _build_export_response(self, export: models.AdminAnalyticsExport) -> AdminAnalyticsExportResponse:
        return AdminAnalyticsExportResponse(
            export_id=str(export.id),
            status=export.status,
            name=export.name,
            path=export.path,
            content_type=export.content_type,
            generated_at=self._to_utc(export.generated_at) if export.generated_at else None,
            expires_at=self._to_utc(export.expires_at) if export.expires_at else None,
            detail=export.detail,
        )

    def _group_events_by_actor(
        self,
        events: Sequence[models.AdminAnalyticsEvent],
    ) -> dict[str, list[models.AdminAnalyticsEvent]]:
        grouped: dict[str, list[models.AdminAnalyticsEvent]] = defaultdict(list)
        for event in events:
            actor_id = self._uuid_to_str(event.actor_user_id)
            if actor_id:
                grouped[actor_id].append(event)
        return grouped

    def _group_system_events(
        self,
        events: Sequence[models.AdminAnalyticsEvent],
    ) -> dict[tuple[str, str], list[models.AdminAnalyticsEvent]]:
        grouped: dict[tuple[str, str], list[models.AdminAnalyticsEvent]] = defaultdict(list)
        for event in events:
            grouped[(event.endpoint_key or "unknown", event.method or "GET")].append(event)
        return grouped

    def _events_for_domain(
        self,
        events: Sequence[models.AdminAnalyticsEvent],
        domain: str,
    ) -> list[models.AdminAnalyticsEvent]:
        return [event for event in events if event.domain == domain]

    def _count_active_users(self, events: Sequence[models.AdminAnalyticsEvent]) -> int:
        return len({self._uuid_to_str(event.actor_user_id) for event in events if event.actor_user_id and event.domain != "system-health"})

    def _average_latency(self, events: Sequence[models.AdminAnalyticsEvent]) -> int:
        latencies = [event.latency_ms for event in events if event.latency_ms is not None]
        if not latencies:
            return 0
        return round(sum(latencies) / len(latencies))

    def _p95_latency(self, events: Sequence[models.AdminAnalyticsEvent]) -> int:
        latencies = sorted(event.latency_ms for event in events if event.latency_ms is not None)
        if not latencies:
            return 0
        index = max(0, ceil(len(latencies) * 0.95) - 1)
        return latencies[index]

    def _previous_period_query(self, query: BaseModel) -> BaseModel:
        delta_days = (getattr(query, "date_to") - getattr(query, "date_from")).days + 1
        return query.model_copy(
            update={
                "date_from": getattr(query, "date_from") - timedelta(days=delta_days),
                "date_to": getattr(query, "date_to") - timedelta(days=delta_days),
            }
        )

    def _period_bounds(self, query: BaseModel) -> tuple[datetime, datetime]:
        return (
            datetime.combine(getattr(query, "date_from"), time.min),
            datetime.combine(getattr(query, "date_to"), time.max),
        )

    def _bucket_for(self, value: datetime, granularity: str) -> tuple[str, str]:
        if granularity == "hour":
            bucket = value.replace(minute=0, second=0, microsecond=0)
            return bucket.strftime("%Y-%m-%dT%H:00:00"), bucket.strftime("%d/%m %H:00")
        if granularity == "week":
            bucket = (value - timedelta(days=value.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            return bucket.date().isoformat(), bucket.strftime("%d/%m")
        if granularity == "month":
            bucket = value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return bucket.strftime("%Y-%m"), bucket.strftime("%m/%Y")
        bucket = value.replace(hour=0, minute=0, second=0, microsecond=0)
        return bucket.date().isoformat(), bucket.strftime("%d/%m")

    def _endpoint_label(self, endpoint_key: str | None, payload: dict[str, Any] | None) -> str:
        if payload and payload.get("label"):
            return str(payload["label"])
        if endpoint_key and endpoint_key in self.SYSTEM_ENDPOINT_LABELS:
            return self.SYSTEM_ENDPOINT_LABELS[endpoint_key]
        return f"/{endpoint_key}" if endpoint_key else "/unknown"

    def _metadata_summary(self, event: models.AdminAnalyticsEvent) -> str | None:
        payload = event.payload or {}
        for key in ("detail", "target_label", "file_name", "layer_name", "search_term", "raster_name"):
            if payload.get(key):
                return str(payload[key])
        if event.endpoint_key:
            return self._endpoint_label(event.endpoint_key, payload)
        return None

    def _actor_name(self, event: models.AdminAnalyticsEvent, user_map: dict[str, models.User]) -> str | None:
        actor_id = self._uuid_to_str(event.actor_user_id)
        if actor_id and actor_id in user_map:
            return user_map[actor_id].user
        return event.actor_name

    def _last_updated_at(
        self,
        items: Sequence[Any],
        fallback: datetime | None = None,
    ) -> datetime:
        timestamps = []
        for item in items:
            if hasattr(item, "occurred_at") and getattr(item, "occurred_at") is not None:
                timestamps.append(getattr(item, "occurred_at"))
            elif hasattr(item, "updated_at") and getattr(item, "updated_at") is not None:
                timestamps.append(getattr(item, "updated_at"))
        if fallback is not None:
            timestamps.append(fallback)
        if not timestamps:
            return datetime.now(timezone.utc)
        latest = max(self._as_naive(value) for value in timestamps)
        return self._to_utc(latest)

    def _user_map(self, users: Sequence[models.User]) -> dict[str, models.User]:
        return {str(user.id): user for user in users}

    def _layer_group_map(self, groups: Sequence[models.LayerGroups]) -> dict[str, models.LayerGroups]:
        return {str(group.id): group for group in groups}

    def _is_admin_user(self, user: models.User) -> bool:
        return bool(user.group and user.group.name == "admin")

    def _matches_search(self, search: str, *values: Any) -> bool:
        return any(search in self._normalized(value) for value in values if value is not None)

    def _normalized(self, value: Any) -> str:
        return str(value or "").strip().lower()

    def _format_number(self, value: int | float) -> str:
        if isinstance(value, float) and not value.is_integer():
            return f"{value:.2f}".replace(",", ".")
        return f"{int(value):,}".replace(",", ".")

    def _sort_value(self, value: Any) -> tuple[int, Any]:
        return (value is None, value)

    def _uuid_to_str(self, value: Any) -> str | None:
        return str(value) if value is not None else None

    def _parse_int(self, value: Any) -> int | None:
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def _as_naive(self, value: datetime) -> datetime:
        return value.replace(tzinfo=None) if value.tzinfo else value

    def _to_utc(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc)
        return value.replace(tzinfo=timezone.utc)