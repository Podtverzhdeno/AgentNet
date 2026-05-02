# Scheduler

## Назначение

Запускает сессии и задачи **по расписанию** или по триггеру. Используется для периодической ре‑верификации решений, обновления данных, регулярных аудитов и мониторинга.

## Ответственности

- Хранить и исполнять расписания (cron‑style + event‑driven).
- Запускать сессии Orchestrator‑а с заданными параметрами.
- Управлять конкурентностью и квотами per‑tenant.
- Учитывать leader election для HA (только один активный шедулер за раз).
- Логировать каждый запуск, его результат и связанную сессию.

## Типы триггеров

| Тип | Пример |
|-----|--------|
| `cron` | `0 6 * * 1-5` — каждый рабочий день в 06:00. |
| `interval` | каждые `30m`. |
| `event` | при появлении нового документа в S3 / новой записи в Kafka. |
| `webhook` | внешний триггер с подписанным payload. |
| `manual` | разовый запуск через UI / CLI. |

## Конфигурация

```yaml
schedules:
  - id: gdpr-audit-monthly
    trigger: { type: cron, expr: "0 7 1 * *" }
    session:
      task: "Проверить продакшн на соответствие GDPR"
      mode: confirm-each-step
    tenant: acme
    enabled: true

  - id: market-research-weekly
    trigger: { type: cron, expr: "0 6 * * 1" }
    session:
      task: "Анализ конкурентов по теме X"
    tenant: acme
```

## API

- `GET  /api/schedules`
- `POST /api/schedules`
- `PATCH /api/schedules/{id}`
- `POST /api/schedules/{id}/run-now`
- `DELETE /api/schedules/{id}`

## Реализация

- Python‑сервис (например, на базе APScheduler или Celery beat) или native LangGraph cron handlers.
- HA: leader election через PostgreSQL advisory lock или etcd.
- Очередь задач на запуск — общая с Orchestrator‑ом (Redis / NATS).

## Безопасность

- Расписания принадлежат тенанту, доступ — только roles `admin` / `scheduler`.
- При запуске сессии используется service account с ограниченными правами.
- Webhook‑триггеры — с подписанным HMAC payload.

## Наблюдаемость

- Метрики: `schedule_runs_total`, `schedule_runs_failed`, `schedule_lag_seconds`.
- Лог: каждый запуск ↔ `session_id`.
- Алерт на `schedule_lag_seconds > X`.

## Failure modes

| Ошибка | Поведение |
|--------|-----------|
| Orchestrator недоступен | задача в retry queue с backoff. |
| Конкурентный лимит превышен | отложить запуск, alert при росте `lag`. |
| Падение лидера | re‑election, текущая итерация может пропуститься. |

## Точки расширения

- Календарные расписания (бизнес‑дни, праздники).
- Зависимости между расписаниями (DAG расписаний).
- ML‑driven scheduling (запускать когда нужнее всего).

## Связанные модули

- [orchestrator.md](orchestrator.md), [observability.md](observability.md), [../INFRASTRUCTURE.md](../INFRASTRUCTURE.md).
