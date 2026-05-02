# Auth & Tenant Isolation

## Назначение

Подсистема `agentnet/auth/` отвечает за резолвинг тенанта из HTTP‑запроса и его трансляцию во все слои платформы (state, persistence, MCP Gateway, vector memory).

В Phase 3.A здесь намеренно нет полноценной OIDC/OAuth — предполагается, что фронт стоит за trusted‑прокси (cluster ingress с mTLS / OIDC), а сюда приходит уже доверенный заголовок. Resolver — точка расширения для подключения JWT‑валидации, OPA, Vault‑auth.

## Резолверы

| Класс                              | Когда использовать |
|------------------------------------|--------------------|
| `StaticTenantResolver(tenant)`     | Single‑tenant deploy. Дефолт `make_app()`. |
| `HeaderTenantResolver(header_name="X-Tenant-Id")` | За trusted‑прокси: ingress кладёт `X-Tenant-Id`, мы доверяем. |
| `BearerTokenTenantResolver({token: tenant})` | Простая токен‑таблица для мульти‑тенантных deployments без OIDC; в проде заменить на JWT‑валидатор. |

Все три реализуют `runtime_checkable` Protocol `TenantResolver` с одним методом `resolve(headers) -> str`.

Фабрика:

```python
from agentnet.auth import make_tenant_resolver

# 1) headers (trusted ingress):
resolver = make_tenant_resolver()                              # HeaderTenantResolver

# 2) bearer tokens:
resolver = make_tenant_resolver(tokens={"acme-key": "acme"})

# 3) single tenant:
resolver = make_tenant_resolver(static="default")
```

## Контракты тенанта в платформе

| Слой         | Где живёт `tenant_id` |
|--------------|----------------------|
| `SessionRequest` (Pydantic) | `tenant_id: str = "default"` |
| `GraphState`   | `tenant_id: str` (TypedDict) |
| Checkpointer | в каждой строке state — никаких отдельных колонок, только поле в JSON |
| `GET /api/sessions` | фильтрует по тенанту, в ответе `{"tenant_id": "...", "threads": [...]}` |
| `GET /api/session/{id}/state` | 404 если запись принадлежит чужому тенанту (не 403, чтобы не leak‑ить факт существования id) |
| `POST /api/session/{id}/approve` | то же самое |
| CLI `session start --tenant <id>` | проставляет `tenant_id` в `SessionRequest` |
| CLI `session list --tenant <id>` / `--all-tenants` | фильтр по сохранённым thread'ам |

## Что **не** входит в Phase 3.A

- Полноценная OIDC / JWT‑валидация (только заглушка `BearerTokenTenantResolver`) — Phase 3.A.2.
- Per‑tenant DB‑роли в Postgres (`SET ROLE tenant_acme`) — Phase 3 после миграции на Postgres.
- Per‑tenant квоты в MCP Gateway (поверх существующего rate‑limit) — Phase 3.A.3.
- Vector store с тенантным префиксом коллекций (сейчас фильтр по `payload.tenant`) — Phase 3.A.4.
- WORM audit log с привязкой ко тенанту — Phase 3.C.

## Связанные модули

- [api.md](api.md) — здесь `make_app(tenant_resolver=...)`.
- [memory.md](memory.md) — все вызовы `VectorStore.upsert/search/delete` уже принимают `tenant`.
- [mcp-gateway.md](mcp-gateway.md) — RBAC по ролям, тенант прокидывается как `principal`.
- [../SECURITY.md](../SECURITY.md).
