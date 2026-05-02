# State Model

Все узлы графа AgentNet работают над **единым объектом состояния** `state`.
Это единый источник истины — узлы читают и пишут только в него.

## Полная схема

```jsonc
{
  // вход
  "idea": "string",                      // исходное описание идеи / запроса пользователя
  "intent": "analysis|design|audit|...", // классификация Orchestrator-ом

  // план
  "plan": {
    "nodes": [
      { "id": 1, "agent": "ResearchAgent", "task": "MarketResearch", "deps": [] }
    ],
    "edges": [ { "from": 1, "to": 4 } ]
  },
  "tasks": [
    { "id": 1, "status": "pending|running|done|failed", "started_at": "...", "ended_at": "..." }
  ],

  // выходы агентов
  "research":     { /* … */ },
  "architecture": { /* … */ },
  "security":     { /* … */ },
  "analytics":    { /* … */ },
  "custom":       { /* … */ },

  // итог итерации
  "result":   "string|object",
  "score":    0.0,
  "feedback": "string|object",

  // мета
  "iteration":   1,
  "max_iterations": 3,
  "session_id":  "XYZ123",
  "user_id":     "...",
  "mode":        "auto|confirm-each-step|manual",
  "trace_id":    "..."
}
```

## Правила обновления

1. **Owner per key.** За каждое поле отвечает ровно один узел:

   | Поле | Owner |
   |------|-------|
   | `idea`, `intent`, `mode` | Orchestrator |
   | `plan`, `tasks` | Planner / Reflector |
   | `research` | Research Agent |
   | `architecture` | Architect Agent |
   | `security` | Security Agent |
   | `analytics` | Analytics Agent |
   | `result` | Aggregator |
   | `score`, `feedback` | Validator |
   | `iteration` | Reflector |

2. **Атомарность.** LangGraph гарантирует атомарную запись delta‑обновления узла.
3. **Idempotency.** Повторный запуск узла на тех же входах не должен менять финальный `state`.
4. **Backward compatible.** Расширения схемы — только добавлением новых ключей.
5. **PII / секреты не хранятся в state.** Используются ссылки на secret‑store или MCP‑резолверы.

## Минимальная схема (TypeScript / Pydantic)

```python
from pydantic import BaseModel, Field
from typing import Any, Literal

class PlanNode(BaseModel):
    id: int
    agent: str
    task: str
    deps: list[int] = []

class Plan(BaseModel):
    nodes: list[PlanNode]
    edges: list[dict] = []

class State(BaseModel):
    idea: str
    intent: Literal["analysis", "design", "audit", "custom"] | None = None
    plan: Plan | None = None
    tasks: list[dict] = []
    research: dict[str, Any] = {}
    architecture: dict[str, Any] = {}
    security: dict[str, Any] = {}
    analytics: dict[str, Any] = {}
    result: Any = None
    score: float = 0.0
    feedback: Any = None
    iteration: int = 1
    max_iterations: int = 3
    session_id: str | None = None
    user_id: str | None = None
    mode: Literal["auto", "confirm-each-step", "manual"] = "auto"
    trace_id: str | None = None
```

## Persistence

- В рантайме `state` живёт в LangGraph state store (Postgres / Redis).
- Каждый шаг создаёт **checkpoint**, который позволяет:
  - возобновить сессию после сбоя,
  - откатиться к предыдущему шагу (time travel),
  - воспроизвести ход рассуждений для аудита.
- По завершении сессии `state` плюс артефакты архивируются в long‑term memory (см. [memory](modules/memory.md)).

## Версионирование

- Схема хранится с указанием `schema_version`.
- Миграции состояния — через явные мигратор‑функции в `agentnet/state/migrations/`.
- Сессии, начатые в одной версии, дочитываются той же версией; новые — в актуальной.
