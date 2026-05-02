# Observability

## Назначение

Сквозная наблюдаемость работы платформы: метрики, логи, трейсы и аудит — для эксплуатации, отладки агентов и регуляторных требований.

## Состав

### Метрики

- Backend: Prometheus + Grafana.
- Метрики каждого модуля описаны в его собственном .md.
- Глобальные метрики:
  - `sessions_total`, `sessions_failed`, `sessions_p95_latency`.
  - `iterations_per_session`.
  - `mcp_calls_total`, `mcp_call_errors`.
  - `sandbox_oom`, `sandbox_kills`.
  - `llm_tokens_total`, `llm_cost_usd_total`.

### Логи

- Структурированный JSON, обязательные поля: `timestamp`, `level`, `service`, `session_id`, `trace_id`, `tenant_id`, `event`.
- Pipeline: app → stdout → Loki / ELK / EFK.
- PII redaction на стороне коллектора и на отправляющей стороне.

### Трейсы

- OpenTelemetry, экспорт в Tempo / Jaeger.
- Root span = сессия; child spans:
  - `planner.run`, `agent.<name>.run`, `aggregator.run`, `validator.run`, `reflector.run`.
  - `mcp.<tool>.call`, `sandbox.<profile>.lifetime`, `memory.search`, `memory.store`.

### LangSmith / agent‑observability

- LangSmith Observability как опциональный layer для подробного дебага LangGraph workflows.
- Запись reasoning‑токенов с маскированием PII.

### Audit

- Отдельный, неизменяемый поток audit‑событий (см. [SECURITY.md](../SECURITY.md)).
- Хранение в WORM bucket / append‑only журнале.
- Доступ через отдельный `audit-service` с RBAC.

## Алертинг

| Алерт | Условие |
|-------|---------|
| `SessionLatencyHigh` | p95 latency > 120s в течение 10 минут. |
| `MCPErrorsSpike` | `mcp_call_errors_rate > 0.05` в течение 5 минут. |
| `SandboxOOM` | `sandbox_oom_total` ↑. |
| `LLMCostSpike` | `llm_cost_usd_total` ↑ > порога. |
| `AuditMissing` | падение потока audit‑событий. |

## Конфигурация

- Helm values для Prometheus / Grafana / Loki / Tempo.
- ServiceMonitor / PodMonitor для модулей.
- OTel Collector deployment + agent на каждом узле.

## Безопасность

- Доступ к Grafana / Tempo / Loki — через SSO + RBAC.
- Логи и трейсы маскируют PII.
- Audit‑данные доступны только compliance‑роли.

## Наблюдаемость самой Observability

- Метрики коллектора и пайплайна.
- Алерты на отсутствие данных от ключевых сервисов.

## Failure modes

| Ошибка | Поведение |
|--------|-----------|
| OTel collector упал | приложения буферизуют и продолжают работу. |
| Prometheus недоступен | алерты на отсутствие данных. |
| Audit pipeline стопится | блокировка операций, требующих write‑side эффектов. |

## Точки расширения

- Подключение SIEM (Splunk / Sentinel) для security‑событий.
- Сэмплирование трейсов по тенантам и стоимости.
- Cost dashboard per‑tenant / per‑agent / per‑skill.

## Связанные модули

- Все модули. См. также [../INFRASTRUCTURE.md](../INFRASTRUCTURE.md), [../SECURITY.md](../SECURITY.md).
