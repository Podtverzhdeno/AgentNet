# Analytics Agent

## Назначение

Работает с данными: проектирует BI‑метрики, готовит SQL‑запросы, прототипирует дашборды и оценивает ROI идеи на исторических данных.

## Ответственности

- Описать целевые KPI и метрики из `idea` и `architecture`.
- Сгенерировать SQL/Python‑шаблоны для расчёта метрик.
- Сделать прогноз / симуляцию (если применимо).
- Сформировать рекомендации по дашбордам и алертам.

## Входы

- `state.idea`, `state.architecture`, `state.research`.
- MCP tools: `db_query` (read‑only), `notebook_run`, `bi_publish`.

## Выходы

- `state.analytics`:
```jsonc
{
  "kpis": [{ "name": "...", "definition": "...", "sql": "..." }],
  "dashboards": [{ "name": "...", "panels": [...] }],
  "forecast": { "method": "...", "result": {...} },
  "roi": { "horizon_months": 12, "estimate": "..." }
}
```

## Взаимодействие со state

Owner: `state.analytics`. Читает `state.idea`, `state.architecture`, `state.research`.

## Зависимости

- Read‑only доступ к корпоративным DB через MCP.
- Notebook runner (опционально) в sandbox.

## Конфигурация

| Параметр | Значение |
|----------|----------|
| `db_role` | `analytics_readonly` |
| `forecast_method_default` | `prophet` |
| `max_query_rows` | 10000 |

## Безопасность

- Все SQL‑запросы — через MCP с whitelisted ролью.
- Никаких write‑операций.
- Данные не сохраняются вне tenant‑isolated storage.

## Наблюдаемость

- Метрики: `queries_executed`, `query_errors`, `notebook_runs`.
- Артефакты: SQL и notebook сохраняются в object storage.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| Запрос превышает лимит | retry с уменьшенной выборкой. |
| Schema mismatch | вернуть ошибку Reflector‑у. |
| Notebook crash | sandbox restart + retry один раз. |

## Точки расширения

- ML‑субагенты (forecasting, anomaly detection).
- Подключение специфичных BI‑инструментов (Superset / Metabase / Power BI).

## Связанные модули

- [agents.md](agents.md), [memory.md](memory.md), [mcp-gateway.md](mcp-gateway.md), [validator.md](validator.md).
