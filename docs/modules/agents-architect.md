# Architect Agent

## Назначение

Превращает результаты ресёрча и идею в **технический дизайн**: модульная декомпозиция, контракты, выбор стека, диаграммы.

## Ответственности

- Получить `state.research` и `state.idea`.
- Сформировать список модулей и их обязанностей.
- Описать API между модулями.
- Подобрать стек технологий с обоснованием.
- Сгенерировать диаграммы (mermaid / C4) и сохранить как артефакты.
- Учесть нефункциональные требования (масштабируемость, latency, стоимость).

## Входы

- `state.idea`, `state.intent`, `state.research`.
- Каталог разрешённых технологий (для корпоративного использования).

## Выходы

- `state.architecture`:
```jsonc
{
  "modules": [
    { "name": "...", "responsibilities": ["..."], "tech": "...", "dependencies": ["..."] }
  ],
  "diagrams": [{ "kind": "mermaid", "uri": "s3://..." }],
  "stack_decisions": [{ "choice": "Postgres", "rationale": "..." }],
  "non_functional": { "latency_p95": "...", "scale": "...", "cost": "..." }
}
```

## Взаимодействие со state

Owner: `state.architecture`. Читает `state.research`.

## Зависимости

- LLM для генерации текста и диаграмм.
- Опционально: tools для проверки согласованности (например, `mermaid_validator`, `openapi_lint`).

## Конфигурация

| Параметр | Значение |
|----------|----------|
| `tech_catalog_path` | `config/tech-catalog.yaml` |
| `diagram_tools` | `["mermaid"]` |
| `min_modules` | 3 |
| `max_modules` | 30 |

## Безопасность

- Не получает права на запись во внешние системы.
- Все артефакты сохраняются в object storage с привязкой к `session_id`.

## Наблюдаемость

- Метрики: `modules_count`, `diagrams_generated`, `stack_decisions`.
- Логи: список выбранных технологий и обоснований.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| Невалидный mermaid/openapi | retry с reformatter. |
| Отсутствует требуемый ресёрч | сообщить Reflector‑у. |

## Точки расширения

- Domain‑шаблоны (банковский back‑end, e‑commerce, аналитический dwh).
- Автоматическое сравнение нескольких вариантов архитектуры по критериям.

## Связанные модули

- [agents.md](agents.md), [agents-research.md](agents-research.md), [aggregator.md](aggregator.md), [validator.md](validator.md).
