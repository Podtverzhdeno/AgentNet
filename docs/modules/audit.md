# Audit Log (WORM, hash-chain)

## Назначение

Подсистема `agentnet/audit/` ведёт **append‑only** журнал событий с tamper‑evident hash‑chain в стиле WORM (Write‑Once, Read‑Many): записать новое событие можно, но переписать старое — нет. Цель — соответствие SOC 2 / ISO‑27001 / GDPR (audit trail), отладка и возможность доказать, что события не подделывались задним числом.

## Структура события

`AuditEvent` (Pydantic):

| Поле        | Семантика |
|-------------|-----------|
| `id`        | `evt-<uuid>`. |
| `timestamp` | unix‑время в момент записи. |
| `tenant_id` | тенант‑владелец (см. [`auth.md`](auth.md)). |
| `actor`     | кто инициировал (user id / service id). |
| `action`    | глагол, например `session.start`, `session.approve`, `tool.call`. |
| `resource`  | id ресурса, к которому относится действие (`thread_id`, `tool_name`, …). |
| `payload`   | произвольные доп. данные (без secrets). |
| `prev_hash` | hash предыдущего события или `"GENESIS"` для первого. |
| `hash`      | `sha256(prev_hash || canonical_json(event_without_hash))`. |

`canonical_json` — `sort_keys=True`, без пробелов, `ensure_ascii=False`. Поэтому одни и те же входные данные при одном и том же `prev_hash` дают воспроизводимый хеш.

## Sinks

| Класс                    | Когда использовать |
|--------------------------|--------------------|
| `InMemoryAuditSink()`    | тесты, single‑process deployments, превью. |
| `FileAuditSink(path)`    | прод: JSON‑lines, `O_APPEND`, переписывание не поддерживается API. |

Контракт `AuditSink` (Protocol): `append(event)`, `__iter__`, `__len__`, `latest_hash()`. Любой свой бэкенд (Postgres + immutable trigger, S3 Object Lock, Loki) реализуется по этому Protocol.

## Recorder

```python
from agentnet.audit import AuditRecorder, FileAuditSink, NewEvent

recorder = AuditRecorder(FileAuditSink("/var/log/agentnet/audit.jsonl"))
recorder.record(NewEvent(
    actor="user-42",
    action="session.start",
    resource="sess-abc123",
    tenant_id="acme",
    payload={"task": "build a kafka consumer"},
))
assert recorder.verify() is True
```

`AuditRecorder` thread‑safe (внутренний `threading.Lock`). При старте читает sink и продолжает chain с последнего `hash` — перезапуск процесса не ломает целостность.

## Интеграция с FastAPI

`make_app(audit_recorder=...)` принимает рекордер и пишет два события из коробки:

| Endpoint                              | action            | payload |
|---------------------------------------|-------------------|---------|
| `POST /api/session/start`             | `session.start`   | `task / mode / max_iterations / score_threshold` |
| `POST /api/session/{id}/approve`      | `session.approve` | `step_id / decision / comment` |

Если рекордер не передан — все хуки no‑op (backward compat).

## Верификация целостности

`recorder.verify()` (или `audit.verify_chain(events)`) перепроверяет каждый `hash` и связку `prev_hash` → `hash`. Возвращает `False` без exception на любом несоответствии — логику тревоги выбирает caller (метрика, alert, лог).

## Что **не** входит в Phase 3.C

- Подпись событий приватным ключом (Phase 3.C.2).
- Запись событий из MCP Gateway (`mcp_gateway/audit.py` пока пишет свой текстовый лог; миграция на общий `AuditRecorder` — Phase 3.C.3).
- Sink на Postgres / S3 Object Lock / Loki — реализуются вне core.
- Стрим аудита в SIEM (Splunk / DataDog) — отдельный adapter.

## Связанные модули

- [auth.md](auth.md) — `tenant_id` в каждом событии.
- [api.md](api.md) — стандартные точки записи.
- [mcp-gateway.md](mcp-gateway.md) — будущий мигрант.
- [../SECURITY.md](../SECURITY.md).
