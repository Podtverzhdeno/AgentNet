# Orchestrator

## Назначение

Точка входа в систему. Принимает запрос пользователя, открывает сессию, инициализирует `state` и управляет верхнеуровневой маршрутизацией по графу LangGraph.

## Ответственности

- Принимать запросы из UI / CLI / API.
- Классифицировать intent (analysis / design / audit / custom).
- Создавать сессию (`session_id`, `trace_id`).
- Инициализировать `state` и persistence backend (Postgres + LangGraph checkpoints).
- Запускать узел Planner, организовывать итерационный цикл `plan → exec → aggregate → validate → reflect`.
- Управлять режимом human‑in‑the‑loop (`auto` / `confirm-each-step` / `manual`).
- Возвращать финальный результат.
- Корректно завершать сессию: успех / failure / max iterations.

## Входы

- HTTP запрос от UI / CLI / внешнего сервиса (`POST /api/session/start`).
- Команды Scheduler‑а (cron‑запуски).
- Approve/reject события от пользователя в режимах с подтверждением.

## Выходы

- Поток обновлений (`SSE` / websocket) в UI/CLI.
- Финальный артефакт сессии (`state.result`).
- Аудит‑события.

## Взаимодействие со state

Owner полей: `idea`, `intent`, `mode`, `session_id`, `user_id`, `trace_id`, `iteration` (init), `max_iterations`.
Не пишет в выходы агентов и `score/feedback`.

## Зависимости

- LangGraph runtime (state store, checkpointer).
- Postgres (или совместимый KV) для persistence.
- Auth / IdP (OIDC) для проверки токенов.
- Observability (OpenTelemetry).

## API / контракты

- `POST /api/session/start` — открыть сессию.
- `GET  /api/session/{id}/state` — текущий `state`.
- `GET  /api/session/{id}/stream` — стрим событий.
- `POST /api/session/{id}/approve` — подтверждение действия.
- `POST /api/session/{id}/cancel` — отменить.

Подробнее — [API_CONTRACTS.md](../API_CONTRACTS.md).

## Конфигурация

| Параметр | Значение по умолчанию |
|----------|----------------------|
| `max_iterations` | 3 |
| `score_threshold` | 0.8 |
| `mode_default` | `auto` |
| `session_timeout` | 30 минут |
| `checkpoint_every` | 1 узел |

## Безопасность

- Все запросы проходят через IdP, токен валидируется.
- Привязывает сессию к `user_id` и `tenant_id`.
- Применяет per‑tenant квоты (rate limit, конкурентность).

## Наблюдаемость

- Метрики: `sessions_started`, `sessions_failed`, `iterations_per_session`, `latency_*`.
- Tracing: root span на сессию, child‑spans на каждый узел графа.
- Структурированные логи с `session_id`, `trace_id`, `tenant_id`.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| Сбой LangGraph runtime | возобновление с последнего checkpoint. |
| Тайм‑аут сессии | `failed` + отчёт пользователю. |
| Отказ агента | передать в Reflector через цикл валидации. |
| `max_iterations` исчерпано | завершить как `failed`, отдать частичный результат. |

## Точки расширения

- Альтернативные классификаторы intent (LLM / rule‑based).
- Подключение новых режимов взаимодействия (например, бот в Slack).
- Гибридные стратегии маршрутизации (skill‑based fast‑path).

## Связанные модули

- [planner.md](planner.md), [aggregator.md](aggregator.md), [validator.md](validator.md), [reflector.md](reflector.md), [scheduler.md](scheduler.md), [ui.md](ui.md), [cli.md](cli.md).
