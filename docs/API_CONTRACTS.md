# API Contracts

Все межмодульные взаимодействия — REST + JSON. Длинно живущие сессии — через server‑sent events / websockets для стриминга промежуточного состояния. Внутри Python‑процесса используется LangGraph граф; API живёт «снаружи» него.

## Orchestrator API

### `POST /api/session/start`

Открывает новую сессию.

```json
{ "task": "Спроектировать аналитическую систему по данным клиентов", "mode": "auto" }
```

**Ответ:**

```json
{
  "session_id": "XYZ123",
  "next": "planner",
  "state": { "idea": "...", "iteration": 1 }
}
```

### `GET /api/session/{id}/state`

Возвращает текущий `state` (с маскированием PII при необходимости).

### `GET /api/session/{id}/stream` (SSE)

Стримит обновления узлов: `node_started`, `node_finished`, `state_patch`, `validation_result`.

### `POST /api/session/{id}/approve`

Подтверждение действия от пользователя в режимах `confirm-each-step` / `manual`.

```json
{ "step_id": 12, "decision": "approve|reject", "comment": "..." }
```

## Planner API

### `POST /api/session/{id}/planner`

Строит DAG.

```json
{ "state": { "idea": "...", "iteration": 1 } }
```

**Ответ:**

```json
{
  "plan": [
    { "id": 1, "agent": "ResearchAgent",  "task": "MarketResearch", "deps": [] },
    { "id": 2, "agent": "ArchitectAgent", "task": "DesignArchitecture", "deps": [1] },
    { "id": 3, "agent": "SecurityAgent",  "task": "SecurityAudit", "deps": [2] }
  ]
}
```

## Worker Agent API (общая форма)

### `POST /api/agents/{name}/run`

```json
{
  "session_id": "XYZ123",
  "task": { "id": 1, "type": "MarketResearch", "details": "..." },
  "state": { /* срез state */ }
}
```

**Ответ:**

```json
{
  "output": "Исследование показало 5 основных конкурентов и тенденцию роста рынка.",
  "confidence": 0.92,
  "artifacts": [{ "kind": "doc", "uri": "s3://..." }]
}
```

## Aggregator API

### `POST /api/session/{id}/aggregate`

```json
{
  "outputs": [
    { "agent": "ResearchAgent",  "output": "..." },
    { "agent": "ArchitectAgent", "output": "..." },
    { "agent": "SecurityAgent",  "output": "..." }
  ]
}
```

**Ответ:**

```json
{ "result": "...", "conflicts": [], "summary": "..." }
```

## Validator API

### `POST /api/session/{id}/validate`

```json
{
  "result": "...",
  "criteria": { "rubric": "default", "weights": { "completeness": 0.4, "security": 0.3, "feasibility": 0.3 } }
}
```

**Ответ:**

```json
{
  "score": 0.68,
  "issues": ["Недостаточно проработана бизнес-модель", "Неохвачены требования GDPR"],
  "feedback": "Добавьте оценку законности проекта и глубину рыночного анализа.",
  "retry": true
}
```

## Reflector API

### `POST /api/session/{id}/reflect`

```json
{ "feedback": "...", "plan": { /* текущий */ } }
```

**Ответ:**

```json
{ "plan": { /* обновлённый DAG */ }, "questions_to_user": [] }
```

## MCP Gateway API

### `POST /mcp/call`

```json
{
  "tool": "query_database",
  "params": { "table": "customers", "filter": "region='EU'" },
  "auth_token": "Bearer <sso-token>"
}
```

**Ответ:**

```json
{ "status": "success", "result": [{ "...": "..." }] }
```

## Memory API

### `POST /api/memory/search`

```json
{ "query": "схожие задачи аналитической платформы", "top_k": 5, "scope": "tenant:acme" }
```

### `POST /api/memory/store`

```json
{ "session_id": "XYZ123", "kind": "skill|artifact|trace", "payload": { /* … */ } }
```

## Skills API

### `GET /api/skills?query=...`

Поиск по библиотеке навыков.

### `POST /api/skills`

Регистрация нового skill (после успешной сессии и одобрения).

## Ошибки

Все эндпоинты возвращают единый формат ошибки:

```json
{
  "error": {
    "code": "validation_failed|tool_blocked|max_iterations|...",
    "message": "human-readable",
    "session_id": "...",
    "trace_id": "..."
  }
}
```

## Аутентификация

- Все запросы требуют bearer‑токен от корпоративного IdP (OIDC).
- Service‑to‑service — mTLS внутри кластера + service account токен.
- Токены к MCP‑инструментам — короткоживущие, выдаются Gateway.
