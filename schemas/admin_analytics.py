from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


AdminAnalyticsGranularity = Literal["hour", "day", "week", "month"]
AdminAnalyticsSortOrder = Literal["asc", "desc"]
AdminAnalyticsTrend = Literal["up", "down", "flat"]
AdminAnalyticsDomain = Literal[
    "overview",
    "user-activity",
    "file-usage",
    "map-usage",
    "admin-operations",
    "system-health",
]
AdminAnalyticsExportFormat = Literal["csv", "xlsx", "json"]
AdminAnalyticsExportStatus = Literal["pending", "ready", "failed"]
AdminAnalyticsAlertLevel = Literal["info", "warning", "critical"]


def _default_date_from() -> date:
    return date.today() - timedelta(days=30)


def _default_date_to() -> date:
    return date.today()


class AdminAnalyticsErrorItem(BaseModel):
    field: str
    message: str


class AdminAnalyticsOptionItem(BaseModel):
    value: str
    label: str


class AdminAnalyticsLayerGroupOption(BaseModel):
    id: str
    name: str


class AdminAnalyticsLayerOption(BaseModel):
    id: str
    name: str
    group_id: str | None = None


class AdminAnalyticsUserOption(BaseModel):
    id: str
    name: str


class AdminAnalyticsEndpointOption(BaseModel):
    key: str
    label: str


class AdminAnalyticsFilterOptionsQuery(BaseModel):
    scope: Literal["all"] = "all"


class AdminAnalyticsBaseQuery(BaseModel):
    date_from: date = Field(default_factory=_default_date_from)
    date_to: date = Field(default_factory=_default_date_to)
    timezone: str = "America/Fortaleza"
    granularity: AdminAnalyticsGranularity = "day"
    compare_previous: bool = True
    search: str = ""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)
    sort_by: str = ""
    sort_order: AdminAnalyticsSortOrder = "desc"

    @model_validator(mode="after")
    def validate_period(self) -> "AdminAnalyticsBaseQuery":
        if self.date_from > self.date_to:
            raise ValueError("date_from deve ser menor ou igual a date_to")
        if not self.timezone.strip():
            raise ValueError("timezone deve ser informado")
        return self


class AdminAnalyticsOverviewQuery(AdminAnalyticsBaseQuery):
    pass


class AdminAnalyticsUserActivityQuery(AdminAnalyticsBaseQuery):
    institution: str | None = None
    occupation: str | None = None
    education: str | None = None
    gender: str | None = None
    age_min: int | None = Field(default=None, ge=0)
    age_max: int | None = Field(default=None, ge=0)
    is_admin: bool | None = None
    user_id: str | None = None
    event_type: str | None = None

    @model_validator(mode="after")
    def validate_age_bounds(self) -> "AdminAnalyticsUserActivityQuery":
        if self.age_min is not None and self.age_max is not None and self.age_min > self.age_max:
            raise ValueError("age_min deve ser menor ou igual a age_max")
        return self


class AdminAnalyticsFileUsageQuery(AdminAnalyticsBaseQuery):
    file_id: str | None = None
    category: str | None = None
    sub_category: str | None = None
    action: str | None = None
    user_id: str | None = None


class AdminAnalyticsMapUsageQuery(AdminAnalyticsBaseQuery):
    layer_id: str | None = None
    layer_group_id: str | None = None
    action: str | None = None
    theme: str | None = None
    raster_name: str | None = None
    search_term: str | None = None


class AdminAnalyticsAdminOperationsQuery(AdminAnalyticsBaseQuery):
    admin_user_id: str | None = None
    action: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    status: str | None = None


class AdminAnalyticsSystemHealthQuery(AdminAnalyticsBaseQuery):
    endpoint: str | None = None
    method: str | None = None
    status_code: int | None = None
    min_latency_ms: int | None = Field(default=None, ge=0)
    max_latency_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_latency_bounds(self) -> "AdminAnalyticsSystemHealthQuery":
        if self.min_latency_ms is not None and self.max_latency_ms is not None and self.min_latency_ms > self.max_latency_ms:
            raise ValueError("min_latency_ms deve ser menor ou igual a max_latency_ms")
        return self


class AdminAnalyticsSummaryCard(BaseModel):
    key: str
    label: str
    value: int | float
    formatted_value: str
    delta_value: int | float | None = None
    delta_label: str | None = None
    trend: AdminAnalyticsTrend | None = None


class AdminAnalyticsAlert(BaseModel):
    key: str
    level: AdminAnalyticsAlertLevel
    label: str
    detail: str


class AdminAnalyticsTimeseriesPoint(BaseModel):
    bucket: str
    label: str
    value: int | float
    compare_value: int | float | None = None


class AdminAnalyticsBreakdownItem(BaseModel):
    key: str
    label: str
    value: int | float
    formatted_value: str
    share: float


class AdminAnalyticsBreakdown(BaseModel):
    key: str
    label: str
    items: list[AdminAnalyticsBreakdownItem]


class AdminAnalyticsActivityEvent(BaseModel):
    id: str
    domain: str
    label: str
    actor_name: str | None = None
    occurred_at: datetime
    metadata_summary: str | None = None


class AdminAnalyticsUserActivityRow(BaseModel):
    user_id: str
    user_name: str
    email: str
    is_admin: bool
    institution: str | None = None
    last_login_at: datetime | None = None
    login_count: int
    active_days: int
    downloads_count: int
    map_actions_count: int


class AdminAnalyticsFileUsageRow(BaseModel):
    file_id: str
    file_name: str
    category: str | None = None
    sub_category: str | None = None
    created_at: datetime
    downloads: int
    unique_users: int
    last_download_at: datetime | None = None


class AdminAnalyticsMapUsageRow(BaseModel):
    layer_id: str
    layer_name: str
    group_id: str | None = None
    group_name: str | None = None
    activated: bool
    created_at: datetime
    views: int
    unique_users: int
    last_viewed_at: datetime | None = None


class AdminAnalyticsAdminOperationRow(BaseModel):
    event_id: str
    action: str
    target_type: str
    target_id: str
    target_label: str
    admin_user_id: str | None = None
    admin_user_name: str | None = None
    status: str
    occurred_at: datetime
    detail: str | None = None


class AdminAnalyticsSystemHealthRow(BaseModel):
    endpoint_key: str
    label: str
    method: str
    status_code: int
    request_count: int
    error_count: int
    avg_latency_ms: int
    p95_latency_ms: int
    last_seen_at: datetime | None = None


class AdminAnalyticsPaginatedUsers(BaseModel):
    page: int
    page_size: int
    total_rows: int
    total_pages: int
    rows: list[AdminAnalyticsUserActivityRow]


class AdminAnalyticsPaginatedFiles(BaseModel):
    page: int
    page_size: int
    total_rows: int
    total_pages: int
    rows: list[AdminAnalyticsFileUsageRow]


class AdminAnalyticsPaginatedLayers(BaseModel):
    page: int
    page_size: int
    total_rows: int
    total_pages: int
    rows: list[AdminAnalyticsMapUsageRow]


class AdminAnalyticsPaginatedOperations(BaseModel):
    page: int
    page_size: int
    total_rows: int
    total_pages: int
    rows: list[AdminAnalyticsAdminOperationRow]


class AdminAnalyticsPaginatedSystemHealth(BaseModel):
    page: int
    page_size: int
    total_rows: int
    total_pages: int
    rows: list[AdminAnalyticsSystemHealthRow]


class AdminAnalyticsUserDetail(BaseModel):
    id: str
    name: str
    email: str
    is_admin: bool
    institution: str | None = None
    occupation: str | None = None
    education: str | None = None
    gender: str | None = None
    age: str | None = None
    created_at: datetime


class AdminAnalyticsFileDetail(BaseModel):
    id: str
    name: str
    path: str
    category: str | None = None
    sub_category: str | None = None
    created_at: datetime


class AdminAnalyticsLayerDetail(BaseModel):
    id: str
    name: str
    subtitle: str
    path: str
    path_icon: str
    group_id: str | None = None
    group_name: str | None = None
    activated: bool
    created_at: datetime


class AdminAnalyticsTopUser(BaseModel):
    user_id: str
    user_name: str
    email: str
    value: int
    formatted_value: str


class AdminAnalyticsOperationDetail(BaseModel):
    event_id: str
    action: str
    target_type: str
    target_id: str
    target_label: str
    admin_user_id: str | None = None
    admin_user_name: str | None = None
    status: str
    occurred_at: datetime
    detail: str | None = None


class AdminAnalyticsEndpointDetail(BaseModel):
    key: str
    label: str
    method: str


class AdminAnalyticsFilterOptionsResponse(BaseModel):
    date_presets: list[str]
    granularities: list[AdminAnalyticsGranularity]
    file_categories: list[AdminAnalyticsOptionItem]
    file_subcategories: list[AdminAnalyticsOptionItem]
    layer_groups: list[AdminAnalyticsLayerGroupOption]
    layers: list[AdminAnalyticsLayerOption]
    admin_users: list[AdminAnalyticsUserOption]
    system_endpoints: list[AdminAnalyticsEndpointOption]
    status_codes: list[int]


class AdminAnalyticsOverviewResponse(BaseModel):
    summary_cards: list[AdminAnalyticsSummaryCard]
    tab_counts: dict[str, int]
    timeseries: list[AdminAnalyticsTimeseriesPoint]
    breakdowns: list[AdminAnalyticsBreakdown]
    alerts: list[AdminAnalyticsAlert]
    recent_activity: list[AdminAnalyticsActivityEvent]
    last_updated_at: datetime


class AdminAnalyticsUserActivityResponse(BaseModel):
    summary_cards: list[AdminAnalyticsSummaryCard]
    timeseries: list[AdminAnalyticsTimeseriesPoint]
    breakdowns: list[AdminAnalyticsBreakdown]
    table: AdminAnalyticsPaginatedUsers
    last_updated_at: datetime


class AdminAnalyticsUserActivityDetailResponse(BaseModel):
    user: AdminAnalyticsUserDetail
    summary_cards: list[AdminAnalyticsSummaryCard]
    timeseries: list[AdminAnalyticsTimeseriesPoint]
    breakdowns: list[AdminAnalyticsBreakdown]
    recent_events: list[AdminAnalyticsActivityEvent]
    last_updated_at: datetime


class AdminAnalyticsFileUsageResponse(BaseModel):
    summary_cards: list[AdminAnalyticsSummaryCard]
    timeseries: list[AdminAnalyticsTimeseriesPoint]
    breakdowns: list[AdminAnalyticsBreakdown]
    table: AdminAnalyticsPaginatedFiles
    last_updated_at: datetime


class AdminAnalyticsFileUsageDetailResponse(BaseModel):
    file: AdminAnalyticsFileDetail
    summary_cards: list[AdminAnalyticsSummaryCard]
    timeseries: list[AdminAnalyticsTimeseriesPoint]
    top_users: list[AdminAnalyticsTopUser]
    recent_events: list[AdminAnalyticsActivityEvent]
    last_updated_at: datetime


class AdminAnalyticsMapUsageResponse(BaseModel):
    summary_cards: list[AdminAnalyticsSummaryCard]
    timeseries: list[AdminAnalyticsTimeseriesPoint]
    breakdowns: list[AdminAnalyticsBreakdown]
    table: AdminAnalyticsPaginatedLayers
    last_updated_at: datetime


class AdminAnalyticsMapUsageDetailResponse(BaseModel):
    layer: AdminAnalyticsLayerDetail
    summary_cards: list[AdminAnalyticsSummaryCard]
    timeseries: list[AdminAnalyticsTimeseriesPoint]
    action_breakdown: list[AdminAnalyticsBreakdownItem]
    recent_events: list[AdminAnalyticsActivityEvent]
    last_updated_at: datetime


class AdminAnalyticsAdminOperationsResponse(BaseModel):
    summary_cards: list[AdminAnalyticsSummaryCard]
    timeseries: list[AdminAnalyticsTimeseriesPoint]
    breakdowns: list[AdminAnalyticsBreakdown]
    table: AdminAnalyticsPaginatedOperations
    last_updated_at: datetime


class AdminAnalyticsAdminOperationDetailResponse(BaseModel):
    operation: AdminAnalyticsOperationDetail
    related_rows: list[AdminAnalyticsAdminOperationRow]
    last_updated_at: datetime


class AdminAnalyticsSystemHealthResponse(BaseModel):
    summary_cards: list[AdminAnalyticsSummaryCard]
    timeseries: list[AdminAnalyticsTimeseriesPoint]
    status_breakdown: list[AdminAnalyticsBreakdownItem]
    latency_buckets: list[AdminAnalyticsBreakdownItem]
    table: AdminAnalyticsPaginatedSystemHealth
    last_updated_at: datetime


class AdminAnalyticsSystemHealthDetailResponse(BaseModel):
    endpoint: AdminAnalyticsEndpointDetail
    summary_cards: list[AdminAnalyticsSummaryCard]
    timeseries: list[AdminAnalyticsTimeseriesPoint]
    status_breakdown: list[AdminAnalyticsBreakdownItem]
    recent_errors: list[AdminAnalyticsActivityEvent]
    last_updated_at: datetime


class AdminAnalyticsExportRequest(BaseModel):
    domain: AdminAnalyticsDomain
    format: AdminAnalyticsExportFormat
    filters: dict[str, Any]
    columns: list[str] | None = None


class AdminAnalyticsExportResponse(BaseModel):
    export_id: str
    status: AdminAnalyticsExportStatus
    name: str
    path: str
    content_type: str
    generated_at: datetime | None = None
    expires_at: datetime | None = None
    detail: str | None = None