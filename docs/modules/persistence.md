# Persistence

## Назначение

Хранение `state` и контрольных точек LangGraph для каждой сессии. Даёт три ключевых свойства:

* **Recovery** — рантайм может перезапуститься и подобрать сессию с последней контрольной точки.
* **Inspectability** — текущее и любое историческое состояние сессии можно прочитать через CLI/API.
* **Replayability** — для отладки можно «промотать» сессию до нужного шага.

В Phase 2 поддерживаются `MemorySaver` (по умолчанию) и `SqliteSaver` (`langgraph-checkpoint-sqlite`). Postgres / Redis перенесены в Phase 3 вместе с мульти‑тенантностью (см. [`../INFRASTRUCTURE.md`](../INFRASTRUCTURE.md)).

## Ответственности

* Создание checkpointer'а по URI (`memory`, `sqlite::memory:`, `sqlite:///path.db`).
* Прозрачная интеграция в [`graph.build_graph`](../../agentnet/graph.py) и [`run_session`](../../agentnet/graph.py).
* Перечисление сохранённых сессий (`list_thread_ids`).
* Чтение последнего состояния по `thread_id` (`get_session_state`).

Не отвечает за:

* Бэкапы / репликацию (это уровень K8s/Postgres).
* Шифрование at‑rest (планируется в Phase 3 через Vault + K8s storage classes).

## Входы / Выходы

| Метод | Вход | Выход |
|-------|------|-------|
| `make_checkpointer(uri)` | URI | `BaseCheckpointSaver` |
| `default_checkpoint_uri()` | — | `sqlite:///~/.agentnet/checkpoints.sqlite` |
| `list_thread_ids(cp)` | checkpointer | `list[str]` distinct thread_ids |
| `get_session_state(tid, cp)` | thread_id, checkpointer | `dict` или `None` |
| `run_session(req, thread_id=…, checkpointer_uri=…)` | request + опции | `SessionResult` |

## Взаимодействие со state

Checkpointer срабатывает после каждого узла. Сохраняется полное `channel_values` (наш `state`) + метаданные шага. При следующем `invoke` с тем же `thread_id` LangGraph возьмёт состояние из последнего чекпоинта.

`thread_id == session_id` — мы умышленно совпадаем эти идентификаторы, чтобы не плодить параллельные ID.

## Зависимости

* `langgraph`, `langgraph-checkpoint-sqlite`.
* `sqlite3` из стандартной библиотеки (open соединения вручную, чтобы не таскать context manager).

## API / Контракты

CLI (см. [`cli.md`](cli.md)):

```bash
agentnet session start "..." --persist sqlite:///~/.agentnet/dev.sqlite --thread-id my-id
agentnet session list  --persist sqlite:///~/.agentnet/dev.sqlite
agentnet session get   my-id --persist sqlite:///~/.agentnet/dev.sqlite
```

Переменная окружения `AGENTNET_CHECKPOINTER` подменяет `--persist` по умолчанию.

## Конфигурация

| Параметр | Значение по умолчанию | Описание |
|----------|----------------------|----------|
| `AGENTNET_CHECKPOINTER` | unset | URI чекпоинтера для всех CLI/API запусков. |
| Disk path | `~/.agentnet/checkpoints.sqlite` | используется в `default_checkpoint_uri()`. |

## Безопасность

* Файл SQLite кладётся в `~/.agentnet` с правами текущего пользователя; для сервера/мульти‑юзера вынести в защищённый volume.
* Не хранить secrets в `state` — checkpointer пишет всё. PII‑guard описан в [`../SECURITY.md`](../SECURITY.md).
* В Phase 3 добавим encryption‑at‑rest и tenant‑scoped роли в Postgres.

## Наблюдаемость

* Лог‑события `session.start` / `session.end` помечены `persisted: true|false` (см. [`observability.md`](observability.md)).
* Размер БД растёт линейно по количеству шагов; рекомендуем периодический VACUUM или ротацию по дате.

## Failure modes & повторы

| Сбой | Поведение |
|------|-----------|
| Запись в SQLite упала (диск, права) | LangGraph поднимает исключение, сессия падает; пользователю возвращается ошибка. |
| Сломанный URI | `make_checkpointer` создаёт директорию, но открытие SQLite даст ошибку — она пробрасывается. |
| Удалили БД во время работы | Поведение SQLite — следующая запись поднимет ошибку. |

Повторы выполняются на уровне LangGraph (узлы повторяются), не на уровне checkpointer'а.

## Точки расширения

* Добавить Postgres‑адаптер: `from langgraph.checkpoint.postgres import PostgresSaver`. Wrapper в `make_checkpointer` для `postgresql://...`.
* Async‑вариант: `AsyncSqliteSaver` (для Phase 2.D / FastAPI).
* Мульти‑тенант: префикс таблицы или отдельные DB по tenant.

## Связанные модули

* [`orchestrator.md`](orchestrator.md) — генерирует / переиспользует `session_id`.
* [`memory.md`](memory.md) — long‑term memory (vector DB) — отдельная подсистема, не путать с checkpointer.
* [`observability.md`](observability.md) — логи и трейсы шагов сессии.
