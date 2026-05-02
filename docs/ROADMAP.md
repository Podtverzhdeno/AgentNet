# Roadmap

Поэтапный план реализации платформы. Цель — как можно раньше получить рабочий MVP, затем наращивать функциональность.

## Phase 0 — Архитектура и каркас

- [x] Архитектурная документация (этот PR).
- [ ] Базовый Python‑скелет (`agentnet/`), линтер, pre‑commit, CI.
- [ ] Helm‑чарт каркас, локальный compose для разработки.

## Phase 1 — MVP (single‑tenant, single‑LLM)

- [x] Orchestrator + Planner + Validator + Reflector на LangGraph.
- [x] Один Worker (Research Agent) с mock‑MCP. *(в Phase 1 сразу 4 worker'а: Research, Architect, Security, Analytics)*
- [x] State persistence (SQLite через `langgraph-checkpoint-sqlite`; Postgres — Phase 3).
- [x] Минимальный CLI (`session start`, `session list`, `session get`).
- [x] HTTP API + SSE стрим (`POST /api/session/start`, `GET /api/session/{id}/state`, `GET /api/session/{id}/stream`, `POST /api/session/{id}/approve`).
- [ ] Минимальный UI (просмотр графа и стрим обновлений).
- [ ] Базовая observability (OTEL traces, Prometheus counters). *(пока только structlog; OTEL/Prometheus — Phase 3)*

## Phase 2 — Полный рабочий цикл

- [ ] Architect Agent, Security Agent, Analytics Agent.
- [ ] Aggregator с разрешением конфликтов.
- [x] Long‑term memory: `VectorStore` Protocol + InMemoryVectorStore + Qdrant‑адаптер + embedder’ы (Hash / OpenAI / Ollama) с тенантной изоляцией (Phase 2.E). RAG‑интеграция в агентов — Phase 2.A.2.
- [x] MCP Gateway с YAML‑конфигом, RBAC, approval‑gate, rate‑limit, аудитом и in‑process / HTTP транспортами (Phase 2.B).
- [ ] Sandbox runtime: Docker + gVisor.
- [ ] Human‑in‑the‑loop checkpoints в UI/CLI.

## Phase 3 — Безопасность и мульти‑тенант

- [ ] Vault + secret resolvers через MCP.
- [ ] Per‑tenant изоляция (namespace, DB role, vector‑prefix).
- [ ] Audit log с WORM‑хранилищем.
- [ ] PII guard и output filter.
- [ ] Sandbox для code‑exec: Firecracker / Kata.

## Phase 4 — Skills & автоматизация

- [ ] Регистрация и переиспользование skills.
- [ ] Scheduler (cron‑задачи, периодическая ре‑верификация решений).
- [ ] Marketplace внутренних агентов и инструментов.
- [ ] Self‑update планов на основе истории.

## Phase 5 — Production hardening

- [ ] DR / backup runbook.
- [ ] Бенчмарки latency / throughput.
- [ ] Полный SOC2 / GDPR compliance pack.
- [ ] HA в нескольких регионах.
- [ ] SDK для подключения новых агентов сторонних команд.

## Открытые вопросы

- Выбор финального стека для long‑term memory (Qdrant vs Pinecone vs Weaviate).
- Решение по sandbox по умолчанию (Docker+gVisor vs Kata).
- Механизм деления оплаты LLM по тенантам.
- Стратегия миграции схемы `state` (см. [STATE_MODEL.md](STATE_MODEL.md#версионирование)).
