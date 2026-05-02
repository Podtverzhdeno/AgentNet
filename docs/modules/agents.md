# Worker Agents (общая модель)

## Назначение

Worker‑агенты — это **исполнители узлов DAG**. Каждый агент решает свой класс задач и пишет результат в соответствующий ключ `state`.

## Общие свойства

- Запускаются Orchestrator‑ом по плану Planner‑а.
- Работают **в собственной песочнице** (см. [sandbox.md](sandbox.md)).
- Все вызовы внешних инструментов — **только** через MCP Gateway.
- Получают на вход срез `state` и описание задачи.
- Могут спавнить **субагентов** (StateGraph subgraphs) для параллельной работы.
- Могут сохранять артефакты в object storage и ссылаться на них из `state`.

## Входы / Выходы

**Вход:**
```json
{
  "session_id": "XYZ123",
  "task": { "id": 1, "type": "...", "details": "..." },
  "state": { /* срез */ }
}
```

**Выход:**
```json
{
  "output": "...",
  "confidence": 0.9,
  "artifacts": [{ "kind": "doc", "uri": "s3://..." }],
  "tool_calls": [{ "tool": "...", "duration_ms": 123 }]
}
```

## Контракт

Каждый агент реализует интерфейс:

```python
class Agent(Protocol):
    name: str
    capabilities: list[str]

    async def run(self, task: Task, state: State) -> AgentResult: ...
```

## Реестр агентов

- Конфигурация в `agentnet/agents/registry.yaml`.
- Поля: `name`, `capabilities`, `image`, `sandbox_profile`, `tools_allowlist`, `quotas`.
- Позволяет добавлять новых агентов без изменения ядра.

## Subagents

- Реализуются как LangGraph subgraphs.
- Имеют **сужённый scope state** (только релевантные поля).
- Их результаты merge‑ятся обратно в state ответственного агента.
- Используются для параллелизации (например, Research → много crawler‑subagents по разным источникам).

## Безопасность

- Минимальный набор прав (capability‑based access).
- Sandbox профиль выбирается по риску задачи.
- Tools — из allowlist, прописанного в реестре.
- Любая сетевая активность — только через прокси с allowlist.

## Наблюдаемость

- Метрики: `agent_runs`, `agent_latency`, `subagents_per_run`, `tool_calls`.
- Trace: span на запуск агента + child span на каждый tool‑call.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| Tool недоступен | retry с backoff, далее — пометить `failed` и продолжить. |
| OOM / timeout | kill контейнера, restart с уменьшенной задачей или escalate в Reflector. |
| Hallucination / низкая confidence | пометить узел и передать в Validator. |

## Точки расширения

- Новые типы агентов добавляются регистрацией в registry без изменения ядра.
- Sub‑agent шаблоны (parallel scrape, parallel test, etc.) могут переиспользоваться.

## Связанные модули

- [planner.md](planner.md), [mcp-gateway.md](mcp-gateway.md), [sandbox.md](sandbox.md), [aggregator.md](aggregator.md), [validator.md](validator.md).
- Конкретные агенты: [agents-research.md](agents-research.md), [agents-architect.md](agents-architect.md), [agents-security.md](agents-security.md), [agents-analytics.md](agents-analytics.md).
