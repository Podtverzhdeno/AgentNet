# Skills

## Назначение

Библиотека **переиспользуемых паттернов решений**. Если система уже успешно решила задачу класса X, она запоминает план + ключевые промпты + конфигурацию агентов как **skill** и при повторном запросе использует его вместо генерации с нуля.

## Что такое skill

Skill — это конфигурационный артефакт со следующими полями:

```jsonc
{
  "id": "skill.security_audit.v1",
  "name": "Security audit of system idea",
  "version": "1.0.0",
  "tags": ["security", "audit", "stride"],
  "trigger": {
    "intent": "audit",
    "keywords": ["безопасность", "угроз", "compliance"]
  },
  "plan_template": { /* DAG с placeholders */ },
  "agent_configs": { "SecurityAgent": { "frameworks": ["GDPR", "SOC2"] } },
  "prompts": { "SecurityAgent": "..." },
  "criteria": { "threshold": 0.85 },
  "metrics": { "avg_score": 0.91, "uses": 17, "success_rate": 0.94 }
}
```

## Жизненный цикл

1. **Discovery.** После N успешных сессий со схожим intent система предлагает превратить план в skill.
2. **Curation.** Пользователь / куратор подтверждает и при необходимости редактирует skill в UI.
3. **Registration.** Skill сохраняется в реестре (БД + git‑репозиторий).
4. **Usage.** Planner на старте проверяет, подходит ли skill к запросу — если да, использует его план как основу.
5. **Evolution.** Метрики (`avg_score`, `success_rate`) обновляются при каждом использовании; неудачные skill переводятся в `deprecated`.

## Ответственности модуля

- Хранить реестр skills (с версионированием).
- Поиск skill по запросу (по тегам, эмбеддингам, intent).
- Применение skill: подстановка placeholders + создание плана.
- Метрики использования и качество.

## API

- `GET  /api/skills?query=...&intent=...` — поиск.
- `POST /api/skills` — регистрация (требует одобрения).
- `GET  /api/skills/{id}` — получить.
- `POST /api/skills/{id}/deprecate` — пометить устаревшим.

## Хранение

- Метаданные — Postgres.
- Тело skill (JSON / YAML) — git‑репозиторий с историей и review.
- Эмбеддинги для поиска — vector DB.

## Конфигурация

| Параметр | Значение |
|----------|----------|
| `auto_promote_after_uses` | 3 |
| `min_success_rate_to_promote` | 0.8 |
| `require_human_approval` | true |

## Безопасность

- Skill не может расширять scope tools агентам, к которым у пользователя нет прав.
- Аудит регистрации и применения каждого skill.

## Наблюдаемость

- Метрики: `skills_count`, `skills_uses`, `skill_match_rate`, `skill_success_rate`.
- Лог: какой skill был выбран, какие placeholders подставлены.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| Несовместимый skill | пропустить, упасть на обычное планирование. |
| Skill устарел | пометить `deprecated`, выбрать следующий по релевантности. |
| Конфликт версий | решается через `version` и `min_compatible_version`. |

## Точки расширения

- Композиция skills (один skill вызывает другой).
- Параметризованные skill (template + variables).
- Marketplace skills между тенантами (с явным согласованием).

## Связанные модули

- [planner.md](planner.md), [memory.md](memory.md), [orchestrator.md](orchestrator.md).
