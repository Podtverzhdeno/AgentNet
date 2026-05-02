# Research Agent

## Назначение

Анализирует рынок, аналоги, литературу, данные, релевантные `state.idea`. Подготавливает фактологическую базу для дальнейших агентов.

## Ответственности

- Сформулировать research‑вопросы из `idea`.
- Запустить поиск через MCP‑тулы: `web_search`, `internal_kb_search`, `vector_memory_search`.
- Спавнить субагентов‑краулеров на разные источники параллельно.
- Свести найденное к структурированному отчёту со ссылками.
- Оценить confidence по каждому утверждению.

## Входы

- `state.idea`, `state.intent`.
- Доступные тулы: `web_search`, `internal_kb_search`, `memory_search`, `pdf_extract`.

## Выходы

- `state.research`:
```jsonc
{
  "questions": ["..."],
  "findings": [
    { "claim": "...", "evidence": [{ "source": "...", "snippet": "..." }], "confidence": 0.9 }
  ],
  "summary": "...",
  "sources": ["..."]
}
```

## Взаимодействие со state

Owner: `state.research`. Читает `state.idea`, `state.plan`.

## Зависимости

- MCP tools: `web_search`, `internal_kb_search`, `memory_search`.
- Long‑term memory (RAG).

## Конфигурация

| Параметр | Значение |
|----------|----------|
| `max_subagents` | 5 |
| `per_source_timeout` | 20s |
| `min_confidence_to_include` | 0.5 |
| `model` | сконфигурированная LLM |

## Безопасность

- Только read‑only тулы.
- Запрос ко внешним источникам идёт через прокси allowlist.
- PII guard на возвращаемые тексты.

## Наблюдаемость

- Метрики: `research_questions`, `subagents_per_run`, `tool_call_count`.
- Артефакты: исходный JSON отчёт + markdown summary.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| Источник недоступен | пометить и продолжить с другими. |
| Слишком мало результатов | расширить запросы, но не более 2 раз. |
| Противоречие в findings | сохранить оба утверждения с пометкой и confidence. |

## Точки расширения

- Подключение специализированных KB (юридические, медицинские, финансовые).
- Domain‑specific subagents (например, для финансового анализа).

## Связанные модули

- [agents.md](agents.md), [memory.md](memory.md), [mcp-gateway.md](mcp-gateway.md), [aggregator.md](aggregator.md).
