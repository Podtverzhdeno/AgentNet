# HTTP API

> Phase 2.D. Контракты — в [`../API_CONTRACTS.md`](../API_CONTRACTS.md). Здесь — как они реализованы и чем отличаются от MVP.

## Назначение

Тонкий FastAPI‑слой над `agentnet.run_session`/`build_graph`, плюс in‑memory шина событий для SSE‑стриминга узлов. Это дверь снаружи (CLI/UI, integration‑тесты, демо), а не `MCP Gateway` (тот выходит наружу — к инструментам).

## Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| `GET`  | `/api/healthz` | liveness, возвращает `{status:"ok", version:"…"}`. |
| `POST` | `/api/session/start` | `StartSessionRequest` → `202 StartSessionResponse{session_id}`. Запускает граф в `BackgroundTasks`. |
| `GET`  | `/api/session/{id}/state` | Последний чекпоинт, `404` если такого треда нет. |
| `GET`  | `/api/session/{id}/stream` | SSE: `session.start`, `node.update`, `session.end`, `session.error`, `approval.recorded`. `data:` всегда — JSON. |
| `POST` | `/api/session/{id}/approve` | HITL stub. Сейчас просто кладёт событие в шину; полноценный pause/resume через LangGraph `interrupt` — следующий PR. |
| `GET`  | `/api/sessions` | Список `thread_id` из текущего checkpointer'а. |

Ошибки — единый формат `{ "error": { "code": ..., ... } }` (см. [`../API_CONTRACTS.md`](../API_CONTRACTS.md#%D0%9E%D1%88%D0%B8%D0%B1%D0%BA%D0%B8)).

## Запуск

```bash
# с in-memory checkpointer (по умолчанию)
uvicorn agentnet.api:app --reload

# с persistent SQLite через AsyncSqliteSaver
AGENTNET_CHECKPOINTER=sqlite:///~/.agentnet/api.sqlite uvicorn agentnet.api:app
```

или программно:

```python
from agentnet.api import make_app

app = make_app(checkpointer_uri="sqlite:///./api.sqlite")
```

В тестах удобно передать готовый `MemorySaver`:

```python
from langgraph.checkpoint.memory import MemorySaver
app = make_app(checkpointer=MemorySaver())
```

## Шина событий (`SessionEventBus`)

* in‑memory pub/sub, ключ — `session_id` = `thread_id`;
* буферизует все события с момента старта сессии и **реплеит** их новым подписчикам — поэтому SSE‑клиенту не обязательно успевать к началу;
* у каждого подписчика своя `asyncio.Queue`, ping‑события каждые 15 секунд при простое, `session.end` закрывает поток.

В Phase 3 заменим на реальный broker (Redis / NATS) — интерфейс `SessionEventBus` останется тот же.

## Интеграция с persistence

Lifespan‑хендлер `make_app` через [`async_checkpointer`](persistence.md) поднимает либо `MemorySaver`, либо `AsyncSqliteSaver` поверх `aiosqlite`, кладёт его в `app.state.checkpointer`, эндпоинты читают через `request.app.state.checkpointer`. Sync CLI продолжает использовать sync `SqliteSaver` поверх того же файла — данные совместимы.

## Аутентификация

Сейчас открыто. В Phase 3 поверх повесим OIDC‑middleware и tenant‑guard, как описано в [`../SECURITY.md`](../SECURITY.md). Пока никаких токенов; ставьте API за внутренним балансировщиком.

## Наблюдаемость

* `api.session.start` / `api.session.error` — structlog логи на каждом старте/падении.
* SSE‑события сами по себе — это уже наблюдаемость для UI; для бэка они проксируются в шину, для прода добавим OTEL spans.

## Failure modes

| Сбой | Поведение |
|------|-----------|
| Падение узла графа | публикуется `session.error`, потом `session.end`. HTTP `start` уже ответил `202` — клиент видит ошибку только в стриме. |
| Подписка на несуществующую сессию | подписчик ждёт первое событие; до 15с + 1× ping; разумно делать `start` до `stream`. |
| `approve` до запуска графа | событие пишется в буфер, граф (когда стартует) увидит его в шине. |

## Точки расширения

* HITL: заменить stub на интеграцию с LangGraph `interrupt()` и `Command(resume=...)`.
* Auth: middleware OIDC + tenant injection в `app.state`.
* Broker: вынести `SessionEventBus` в `agentnet/api/bus.py` с реализацией поверх Redis Pub/Sub или NATS.
* WebSocket вариант стрима для двунаправленной связи (HITL approve поверх того же сокета).

## Связанные модули

* [`persistence.md`](persistence.md) — общий чекпоинтер.
* [`orchestrator.md`](orchestrator.md), [`planner.md`](planner.md) — узлы графа, события которых стримятся.
* [`cli.md`](cli.md) — CLI повторяет те же операции локально.
