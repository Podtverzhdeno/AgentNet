# Reflector

## Назначение

Превращает обратную связь Validator‑а в **изменённый план**. Отвечает за «умный retry»: не просто перезапуск, а коррекцию стратегии.

## Ответственности

- Проанализировать `state.feedback` и `state.issues`.
- Выявить, какие узлы DAG нужно перезапустить, какие добавить, какие удалить.
- Сформулировать уточняющие вопросы пользователю при необходимости.
- Обновить `state.plan` и инкрементировать `state.iteration`.
- Переключить управление обратно на Planner или сразу на нужные узлы.

## Входы

- `state.feedback`, `state.issues`.
- Текущий `state.plan` и история выполнения.

## Выходы

- Обновлённый `state.plan`.
- `state.iteration += 1`.
- Опционально: `state.questions_to_user` для human‑in‑the‑loop.

## Взаимодействие со state

Owner: `state.plan` (на повторных итерациях), `state.iteration`, `state.questions_to_user`.

## Зависимости

- LLM с reasoning‑моделью.
- Каталог агентов и инструментов (для понимания, кого добавить).

## Конфигурация

| Параметр | Значение |
|----------|----------|
| `max_iterations` | 3 |
| `min_score_delta_for_retry` | 0.05 |
| `escalate_to_user_after` | 2 |

## Безопасность

- Не имеет права привлекать роли/тулы вне scope сессии.
- При запросе к пользователю — текст проходит PII guard.

## Наблюдаемость

- Метрики: `reflections_total`, `plan_diff_nodes_added/removed`, `escalations_to_user`.
- Лог: diff между старым и новым `plan`.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| Нечёткий feedback | сгенерировать вопрос пользователю. |
| Невозможно улучшить план | завершить сессию как `failed` с объяснением. |
| Бесконечный цикл | срабатывает `max_iterations`. |

## Точки расширения

- Подключение reasoning‑агентов с разной стратегией (analytical / creative / conservative).
- A/B сравнение новой и старой версии плана.

## Связанные модули

- [validator.md](validator.md), [planner.md](planner.md), [orchestrator.md](orchestrator.md).
