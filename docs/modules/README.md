# Модули AgentNet

Каждый файл в этой директории описывает один модуль платформы по единому шаблону:

1. **Назначение.**
2. **Ответственности.**
3. **Входы / Выходы.**
4. **Взаимодействие со `state`.**
5. **Зависимости.**
6. **API / контракты.**
7. **Конфигурация.**
8. **Безопасность.**
9. **Наблюдаемость.**
10. **Failure modes & повторы.**
11. **Точки расширения.**
12. **Связанные модули.**

## Список модулей

| Слой | Модуль | Файл |
|------|--------|------|
| Workflow | Orchestrator | [orchestrator.md](orchestrator.md) |
| Workflow | Planner | [planner.md](planner.md) |
| Workflow | Aggregator | [aggregator.md](aggregator.md) |
| Workflow | Validator | [validator.md](validator.md) |
| Workflow | Reflector | [reflector.md](reflector.md) |
| Workflow | Scheduler | [scheduler.md](scheduler.md) |
| Workflow | Persistence (checkpointer) | [persistence.md](persistence.md) |
| Agents   | Worker Agents (общее) | [agents.md](agents.md) |
| Agents   | Research Agent | [agents-research.md](agents-research.md) |
| Agents   | Architect Agent | [agents-architect.md](agents-architect.md) |
| Agents   | Security Agent | [agents-security.md](agents-security.md) |
| Agents   | Analytics Agent | [agents-analytics.md](agents-analytics.md) |
| Memory   | Memory | [memory.md](memory.md) |
| Memory   | Skills | [skills.md](skills.md) |
| Edge     | MCP Gateway | [mcp-gateway.md](mcp-gateway.md) |
| Edge     | Sandbox | [sandbox.md](sandbox.md) |
| Edge     | UI | [ui.md](ui.md) |
| Edge     | CLI | [cli.md](cli.md) |
| Platform | Observability | [observability.md](observability.md) |

См. также:
- [../ARCHITECTURE.md](../ARCHITECTURE.md) — общая архитектура и схемы.
- [../RUNTIME_WORKFLOW.md](../RUNTIME_WORKFLOW.md) — как модули взаимодействуют во времени.
- [../STATE_MODEL.md](../STATE_MODEL.md) — единый объект `state` и правила обновления.
- [../SECURITY.md](../SECURITY.md) — модель угроз и защиты.
