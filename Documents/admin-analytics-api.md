# Contrato da API de Analytics Administrativo

## Regras de autenticacao

1. Todas as rotas abaixo exigem `Authorization: Bearer <access_token>`.
2. O frontend segue o fluxo atual da aplicacao: tentativa unica de refresh por `POST /refresh-token` com corpo `{ "refresh_token": "..." }` quando ocorrer `401`.
3. O backend deve responder:
   - `401` para token invalido ou expirado.
   - `403` para usuario autenticado sem permissao administrativa.
   - `422` para filtros ou payloads invalidos.
4. O formato de erro deve seguir o padrao:

```json
{
  "detail": "Mensagem de erro",
  "errors": [
    {
      "field": "date_from",
      "message": "Campo obrigatorio"
    }
  ]
}
```

## Rotas novas necessarias

### 1. `GET /admin-analytics/filter-options`

Retorna opcoes para os filtros dinamicos do dashboard.

Query:

```json
{
  "scope": "all"
}
```

Resposta:

```json
{
  "date_presets": ["7d", "30d", "90d", "365d"],
  "granularities": ["hour", "day", "week", "month"],
  "file_categories": [{ "value": "Mapa", "label": "Mapa" }],
  "file_subcategories": [{ "value": "solar", "label": "Solar" }],
  "layer_groups": [{ "id": "group-1", "name": "Infraestrutura" }],
  "layers": [{ "id": "layer-1", "name": "Aerodromos", "group_id": "group-1" }],
  "admin_users": [{ "id": "user-1", "name": "Equipe Admin" }],
  "system_endpoints": [{ "key": "file-list", "label": "/file" }],
  "status_codes": [200, 401, 403, 500]
}
```

### 2. `GET /admin-analytics/overview`

Retorna a visao geral do painel.

Query base:

```json
{
  "date_from": "2026-04-01",
  "date_to": "2026-05-14",
  "granularity": "day",
  "compare_previous": true,
  "search": "",
  "page": 1,
  "page_size": 25,
  "sort_by": "",
  "sort_order": "desc"
}
```

Resposta:

```json
{
  "summary_cards": [
    {
      "key": "active_users",
      "label": "Usuarios ativos",
      "value": 324,
      "formatted_value": "324",
      "delta_value": 12,
      "delta_label": "+12% vs. periodo anterior",
      "trend": "up"
    }
  ],
  "tab_counts": {
    "user_activity": 324,
    "file_usage": 186,
    "map_usage": 925,
    "admin_operations": 47,
    "system_health": 18
  },
  "alerts": [
    {
      "key": "error-spike",
      "level": "warning",
      "label": "Aumento de erros 500",
      "detail": "O endpoint /file apresentou crescimento de falhas nas ultimas 24 horas."
    }
  ],
  "recent_activity": [
    {
      "id": "evt-1",
      "domain": "file-usage",
      "label": "Download de relatorio",
      "actor_name": "Equipe Senai",
      "occurred_at": "2026-05-14T10:22:00Z",
      "metadata_summary": "Relatorio solar"
    }
  ],
  "last_updated_at": "2026-05-14T10:30:00Z"
}
```

### 3. `GET /admin-analytics/user-activity`

Filtros adicionais: `institution`, `occupation`, `education`, `gender`, `age_min`, `age_max`, `is_admin`, `user_id`, `event_type`.

Resposta:

```json
{
  "summary_cards": [],
  "timeseries": [
    {
      "bucket": "2026-05-10",
      "label": "10/05",
      "value": 42,
      "compare_value": 35
    }
  ],
  "breakdowns": [
    {
      "key": "institution",
      "label": "Instituicoes",
      "items": [
        {
          "key": "senai",
          "label": "SENAI",
          "value": 18,
          "formatted_value": "18",
          "share": 0.43
        }
      ]
    }
  ],
  "table": {
    "page": 1,
    "page_size": 25,
    "total_rows": 1,
    "total_pages": 1,
    "rows": [
      {
        "user_id": "user-1",
        "user_name": "Maria Silva",
        "email": "maria@example.com",
        "is_admin": false,
        "institution": "SENAI",
        "last_login_at": "2026-05-14T08:15:00Z",
        "login_count": 12,
        "active_days": 8,
        "downloads_count": 3,
        "map_actions_count": 24
      }
    ]
  },
  "last_updated_at": "2026-05-14T10:30:00Z"
}
```

### 4. `GET /admin-analytics/user-activity/{user_id}`

Resposta com entidade do usuario, cards, series, breakdowns e eventos recentes.

### 5. `GET /admin-analytics/file-usage`

Filtros adicionais: `file_id`, `category`, `sub_category`, `action`, `user_id`.

Retorna `summary_cards`, `timeseries`, `breakdowns`, `table` de `AdminAnalyticsFileUsageRow` e `last_updated_at`.

### 6. `GET /admin-analytics/file-usage/{file_id}`

Retorna `file`, `summary_cards`, `timeseries`, `top_users`, `recent_events` e `last_updated_at`.

### 7. `GET /admin-analytics/map-usage`

Filtros adicionais: `layer_id`, `layer_group_id`, `action`, `theme`, `raster_name`, `search_term`.

Retorna `summary_cards`, `timeseries`, `breakdowns`, `table` de `AdminAnalyticsMapUsageRow` e `last_updated_at`.

### 8. `GET /admin-analytics/map-usage/{layer_id}`

Retorna `layer`, `summary_cards`, `timeseries`, `action_breakdown`, `recent_events` e `last_updated_at`.

### 9. `GET /admin-analytics/admin-operations`

Filtros adicionais: `admin_user_id`, `action`, `target_type`, `target_id`, `status`.

Retorna `summary_cards`, `timeseries`, `breakdowns`, `table` de `AdminAnalyticsAdminOperationRow` e `last_updated_at`.

### 10. `GET /admin-analytics/admin-operations/{event_id}`

Retorna `operation`, `related_rows` e `last_updated_at`.

### 11. `GET /admin-analytics/system-health`

Filtros adicionais: `endpoint`, `method`, `status_code`, `min_latency_ms`, `max_latency_ms`.

Retorna `summary_cards`, `timeseries`, `status_breakdown`, `latency_buckets`, `table` de `AdminAnalyticsSystemHealthRow` e `last_updated_at`.

### 12. `GET /admin-analytics/system-health/{endpoint_key}`

Retorna `endpoint`, `summary_cards`, `timeseries`, `status_breakdown`, `recent_errors` e `last_updated_at`.

### 13. `POST /admin-analytics/export`

Corpo:

```json
{
  "domain": "file-usage",
  "format": "csv",
  "filters": {
    "date_from": "2026-04-01",
    "date_to": "2026-05-14",
    "granularity": "day",
    "category": "Mapa"
  },
  "columns": ["file_name", "downloads", "unique_users"]
}
```

Resposta:

```json
{
  "export_id": "exp-1",
  "status": "ready",
  "name": "analytics-file-usage-2026-05-14.csv",
  "path": "/exports/analytics-file-usage-2026-05-14.csv",
  "content_type": "text/csv",
  "generated_at": "2026-05-14T10:31:00Z",
  "expires_at": "2026-05-15T10:31:00Z",
  "detail": null
}
```

### 14. `GET /admin-analytics/export/{export_id}`

Retorna o mesmo schema de exportacao para polling ou recuperacao do status.

## Schemas compartilhados

### Query base

```json
{
  "date_from": "2026-04-01",
  "date_to": "2026-05-14",
  "timezone": "America/Fortaleza",
  "granularity": "day",
  "compare_previous": true,
  "search": "",
  "page": 1,
  "page_size": 25,
  "sort_by": "downloads",
  "sort_order": "desc"
}
```

### Card de indicador

```json
{
  "key": "downloads_total",
  "label": "Downloads totais",
  "value": 1820,
  "formatted_value": "1.820",
  "delta_value": 8,
  "delta_label": "+8% vs. periodo anterior",
  "trend": "up"
}
```

### Ponto de serie temporal

```json
{
  "bucket": "2026-05-01",
  "label": "01/05",
  "value": 91,
  "compare_value": 74
}
```

### Item de breakdown

```json
{
  "key": "mapa",
  "label": "Mapa",
  "value": 120,
  "formatted_value": "120",
  "share": 0.42
}
```

### Estrutura paginada de tabela

```json
{
  "page": 1,
  "page_size": 25,
  "total_rows": 120,
  "total_pages": 5,
  "rows": []
}
```

## Verificacao da API

1. Validar `401`, `403` e `422` em pelo menos uma rota de analytics.
2. Validar retorno vazio com schema valido em cada dominio.
3. Validar filtros globais e filtros especificos por dominio.
4. Validar detalhes por `user_id`, `file_id`, `layer_id`, `event_id` e `endpoint_key`.
5. Validar exportacao pronta e exportacao pendente.
6. Validar que os nomes de campos retornados coincidem com o cliente em `pages/adminAnalytics/script.js`.