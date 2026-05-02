# Validator

## Назначение

Оценивает агрегированный результат по заранее определённым критериям, формирует `score` и структурированный `feedback`. Решает, нужна ли итерация.

## Ответственности

- Прогнать `state.result` через rubric / тесты / правила.
- Рассчитать `score: float ∈ [0, 1]`.
- Сформировать список `issues` с привязкой к разделам.
- Вернуть флаг `retry` (если `score < threshold`).
- При `score >= threshold` зафиксировать решение и передать управление Orchestrator‑у на финиш.

## Входы

- `state.result`, `state.research`, `state.architecture`, `state.security`, `state.analytics`.
- `criteria` (rubric) — глобально для домена + override на сессию.

## Выходы

- `state.score`, `state.feedback`, `state.issues`.
- Решение о `retry`.

## Взаимодействие со state

Owner: `state.score`, `state.feedback`, `state.issues`. Только читает остальные поля.

## Зависимости

- LLM judge.
- Опционально: rule‑engine (например, OPA / Cedar) для строгих проверок.

## Конфигурация

| Параметр | Значение |
|----------|----------|
| `threshold` | 0.8 |
| `weights` | `{completeness: 0.4, security: 0.3, feasibility: 0.3}` |
| `judge_model` | сконфигурированная LLM |
| `use_rule_engine` | true |

## Безопасность

- Запрет на write куда‑либо, кроме `state.score|feedback|issues`.
- LLM judge не получает PII (фильтрация на входе).

## Наблюдаемость

- Метрики: `validation_runs`, `score_avg`, `score_p50`, `retry_rate`.
- Артефакты: полный отчёт валидации сохраняется в object storage.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| LLM вернул невалидный JSON | retry до 2 раз. |
| Rule‑engine отверг результат | `retry=true` со списком явных нарушений. |
| Score нестабилен между вызовами | усреднение по N прогонам. |

## Точки расширения

- Domain‑specific rubrics (банковский продукт, медицинский анализ).
- Подключение human evaluator‑ов (опциональный шаг подтверждения).
- Активные тесты (запуск кода в sandbox с проверкой результатов).

## Связанные модули

- [aggregator.md](aggregator.md), [reflector.md](reflector.md), [orchestrator.md](orchestrator.md).
