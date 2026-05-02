# MCP Gateway

## Назначение

Единая точка доступа от агентов ко внешним инструментам и данным. Реализует **trust boundary**: агенты ничего не могут делать снаружи, минуя Gateway.

## Ответственности

- Аутентификация вызывающего агента (service account / OIDC token).
- Авторизация по RBAC (per‑tool, per‑role, per‑tenant).
- Маршрутизация запросов к MCP‑серверам (FastMCP / Prefect Horizon).
- Применение rate‑limit, квот и timeouts.
- Аудит каждого вызова.
- PII guard на входе/выходе.
- Управление короткоживущими токенами для downstream‑сервисов.

## Реализация

- Базовая платформа: **Prefect Horizon** (готовый MCP gateway) или собственная FastAPI‑обёртка над **FastMCP**.
- Деплой: HA Deployment в Kubernetes, mTLS со всеми клиентами.

## API

### `POST /mcp/call`

```json
{
  "tool": "query_database",
  "params": { "table": "customers", "filter": "region='EU'" }
}
```

Заголовки: `Authorization: Bearer <agent-token>`, `X-Session-Id`, `X-Tenant-Id`, `X-Trace-Id`.

**Ответ:**

```json
{ "status": "success", "result": [{}], "duration_ms": 142 }
```

### `GET /mcp/tools`

Каталог доступных инструментов (фильтруется по правам вызывающего).

## Конфигурация

| Параметр | Значение |
|----------|----------|
| `default_timeout` | 30s |
| `default_rate_limit` | 60 RPM |
| `audit_sink` | WORM bucket |
| `secret_provider` | Vault |

Per‑tool конфигурация:
```yaml
tools:
  query_database:
    backend: "postgres-bi"
    role: "analytics_readonly"
    timeout: 15s
    rate_limit: 30 RPM
    require_approval: false
  bi_publish:
    backend: "superset"
    role: "bi_writer"
    require_approval: true
```

## RBAC

Матрица: `(role, tool) -> {allow|deny|approval}`.

```yaml
roles:
  ResearchAgent:
    allow: [web_search, internal_kb_search, memory_search]
  AnalyticsAgent:
    allow: [query_database, notebook_run]
    approval: [bi_publish]
  SecurityAgent:
    allow: [vuln_db_search, policy_check]
```

## Безопасность

- Все запросы — через mTLS.
- Секреты к downstream‑системам не передаются вызывающему: Gateway сам применяет токен из Vault.
- Ответы фильтруются на PII / секреты.
- Hard‑blocked патерны (например, SQL `DROP TABLE`) — отклоняются на уровне Gateway.

## Наблюдаемость

- Метрики: `mcp_calls_total`, `mcp_call_latency_p95`, `mcp_call_errors`, `mcp_blocked`.
- Audit‑лог: full request/response с `trace_id`, маскированием PII.
- Tracing: child span на каждый downstream‑вызов.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| Downstream timeout | retry с backoff (макс 2 раза). |
| Auth fail | 401 без retry. |
| Rate limit hit | 429 с `Retry-After`. |
| Policy violation | 403 + лог + уведомление security. |

## Точки расширения

- Подключение новых MCP‑серверов через декларативный конфиг.
- Pluggable PII‑detector / output‑filter.
- Поддержка streaming‑ответов от downstream LLM/tools.

## Связанные модули

- [agents.md](agents.md), [sandbox.md](sandbox.md), [observability.md](observability.md).
