# PII Guard

## Назначение

Защита от утечки PII / секретов **до** того, как текст уходит во внешний LLM или пишется в long‑term memory. Реализуется в `agentnet/pii/`.

## Компоненты

| Компонент            | Что делает |
|----------------------|-----------|
| `PIIPattern`, `PIIType` | Именованный regex (email / phone / credit‑card / SSN / JWT / API key / custom). |
| `DEFAULT_PATTERNS`   | Кортеж дефолтных паттернов в порядке приоритета (более специфичные раньше). |
| `Redactor`           | `find(text) → list[Finding]`, `redact(text) → str`, `redact_payload(json_like) → json_like`. Не ходит в сеть. |
| `ScrubbedLLMClient(inner, *, scrub_prompt=True, scrub_response=False)` | Декоратор `LLMClient`, прогоняющий prompts и/или responses через `Redactor`. |

## Использование

```python
from agentnet.llm import make_llm_client
from agentnet.pii import Redactor, ScrubbedLLMClient

# обернуть любой клиент:
inner = make_llm_client("openai:gpt-4o-mini")
client = ScrubbedLLMClient(inner)                 # prompts scrubbed, response untouched
strict = ScrubbedLLMClient(inner, scrub_response=True)  # scrub both directions

# одиночный вызов:
clean = Redactor().redact("call alice@example.com (415) 555-1234")
# → "call [REDACTED:EMAIL] [REDACTED:PHONE]"
```

Для long‑term memory:

```python
from agentnet.memory import MemoryRecord
from agentnet.pii import Redactor

red = Redactor()
record = MemoryRecord(
    text=red.redact(user_input),
    payload=red.redact_payload(metadata),
    tenant=tenant,
)
store.upsert([record])
```

## Безопасность

- Паттерны намеренно консервативны: лучше пропустить «грязное» поле, чем сломать фактический prompt — false positives режут смысл диалога с LLM.
- Перекрытие совпадений детерминированное: первый по порядку паттерн «занимает» спан, более общий уже не сработает (поэтому JWT не помечается как generic API key).
- `Redactor` потокобезопасен (только чтение).

## Что **не** входит в Phase 3.B

- Машинное обучение / LLM‑классификатор PII — Phase 3.B.2.
- Локализация (русские номера, паспорта, ИНН) — Phase 3.B.3.
- Auto‑пересохранение `MemoryRecord.text` через wrapper `VectorStore` — Phase 3.B.4 (сейчас вручную через `redactor.redact`).
- HTTP‑эндпоинт `/api/pii/scan` — Phase 3.

## Связанные модули

- [llm.md](llm.md) — точка интеграции через `ScrubbedLLMClient`.
- [memory.md](memory.md) — `redactor.redact` перед `store.upsert`.
- [../SECURITY.md](../SECURITY.md) — общая модель угроз.
