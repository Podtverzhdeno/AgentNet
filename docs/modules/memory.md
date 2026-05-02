# Memory

## Назначение

Подсистема памяти платформы: хранит **краткосрочный** контекст текущей сессии и **долгосрочный** опыт между сессиями. Обеспечивает RAG для агентов.

## Слои

### Short‑term memory

- **Что:** поле `state` в LangGraph, плюс short‑term cache (Redis) для ускорения частых обращений.
- **Срок:** время жизни сессии + N часов после завершения.
- **Хранилище:** Postgres + Redis.

### Long‑term memory

- **Что:** агрегированные данные из прошлых сессий — embedding‑и идей, finalized артефакты, успешные решения.
- **Срок:** долгосрочно, с per‑tenant TTL и правом на удаление (GDPR).
- **Хранилище:** векторная БД (Qdrant / Pinecone / Weaviate) + object storage (S3/MinIO) для blob‑артефактов.

### Knowledge base

- **Что:** статичные корпоративные данные (вики, документация, регламенты).
- **Использование:** базовый RAG для Research Agent.
- **Хранилище:** vector DB + S3 (источники).

## Ответственности

- Хранить и индексировать контекст и артефакты.
- Предоставлять API поиска (RAG‑style).
- Гарантировать tenant‑isolation.
- Обеспечивать TTL и right‑to‑erasure.

## API

- `POST /api/memory/search` — поиск по эмбеддингам + фильтрам.
- `POST /api/memory/store` — сохранить новый артефакт.
- `DELETE /api/memory/{id}` — удалить (soft, с аудитом).

## Конфигурация

| Параметр | Значение |
|----------|----------|
| `vector_backend` | `qdrant` |
| `embedding_model` | сконфигурированная модель |
| `default_top_k` | 5 |
| `tenant_isolation` | `key prefix tenant:<id>:` |
| `ttl_default` | 365 дней |

## Безопасность

- Поиск всегда ограничен `tenant_id`.
- PII guard перед сохранением.
- Аудит всех `store/search/delete`.

## Наблюдаемость

- Метрики: `memory_search_qps`, `memory_search_latency_p95`, `memory_store_qps`, `memory_size_bytes`.
- Логи: query + filter (без raw‑content).

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| Vector DB недоступна | fallback на чистый LLM без RAG, пометка в логе. |
| Эмбеддинг‑модель упала | retry с альтернативной моделью. |
| Превышение квоты | отказ с явной ошибкой. |

## Точки расширения

- Multi‑modal memory (image / audio embeddings).
- Hierarchical memory (summaries → детали).
- Personal memory per user внутри тенанта.

## Связанные модули

- [skills.md](skills.md), [agents-research.md](agents-research.md), [orchestrator.md](orchestrator.md).

---

## Реализация (Phase 2.E)

`agentnet/memory/` теперь содержит реальный векторный слой:

| Файл           | Содержание |
|----------------|-----------|
| `types.py`     | `MemoryRecord`, `MemoryHit` (Pydantic). |
| `embeddings.py`| `Embedder` Protocol + `HashEmbedder` (детерминированный, без сети) + `OpenAIEmbedder` (`/v1/embeddings`) + `OllamaEmbedder` (`/api/embeddings`). |
| `store.py`     | `VectorStore` Protocol + `InMemoryVectorStore` (cosine‑similarity in‑process, потокобезопасный). |
| `qdrant.py`    | `QdrantVectorStore` поверх REST API Qdrant (`/collections/.../points/{search,delete}`). Авто‑создаёт коллекцию по нужной размерности. |
| `factory.py`   | `make_vector_store(spec, *, embedder=, collection=, base_url=, api_key=)` — резолв `AGENTNET_MEMORY` / `QDRANT_URL` / `QDRANT_API_KEY` / `QDRANT_COLLECTION`. |
| `legacy.py`    | Старый `InMemoryStore` / `MemoryItem` (substring search) — оставлен для обратной совместимости. |

### Тенантная изоляция

Все три операции (`upsert / search / delete`) принимают `tenant`:

- `InMemoryVectorStore.search` фильтрует кандидатов по `record.tenant` **до** косинусного скоринга.
- `QdrantVectorStore.search` отправляет фильтр `must: [{key: "tenant", match: {value: tenant}}]` в Qdrant.
- `QdrantVectorStore.delete` накладывает тот же фильтр + список id, поэтому удалить чужой `id` нельзя даже зная его.

### Использование

```python
from agentnet.memory import make_vector_store, MemoryRecord

# CI / dev (без зависимостей):
store = make_vector_store(None)                 # → InMemoryVectorStore + HashEmbedder

# с Qdrant (env QDRANT_URL/QDRANT_API_KEY/QDRANT_COLLECTION):
store = make_vector_store("qdrant")

# или явные kwargs:
store = make_vector_store(
    "qdrant",
    base_url="https://qdrant.example",
    collection="agentnet",
    api_key="qd-...",
)

store.upsert([MemoryRecord(text="JWT review notes", tenant="acme")])
hits = store.search("auth token", tenant="acme", top_k=3)
```

### Что **не** входит в Phase 2.E

- Подключение `VectorStore` в Research Agent (RAG) — сделаем в Phase 2.A.2.
- TTL и right‑to‑erasure (GDPR) — Phase 3.
- Hybrid search (BM25 + vector) — Phase 3.
- Multi‑modal эмбеддинги (image/audio) — Phase 3.
- HTTP‑эндпоинты `/api/memory/*` — Phase 3 (сейчас слой используется in‑process).
