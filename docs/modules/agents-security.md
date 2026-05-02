# Security Agent

## Назначение

Оценивает идею и предложенную архитектуру с точки зрения **безопасности и комплаенса**: угрозы, уязвимости, GDPR/SOC2/PCI применимость, mitigations.

## Ответственности

- Прогнать threat modeling (STRIDE / LINDDUN / привилегии).
- Сопоставить регуляторные требования (GDPR, ФЗ‑152, PCI DSS — в зависимости от тенанта).
- Указать **mitigations** для каждой угрозы.
- Проверить план на запрещённые действия и опасные тулы.

## Входы

- `state.idea`, `state.architecture`.
- Регуляторные шаблоны и checklists.
- Tools: `vuln_db_search`, `policy_check`.

## Выходы

- `state.security`:
```jsonc
{
  "threats": [
    { "category": "Tampering", "asset": "...", "risk": "high", "mitigation": "..." }
  ],
  "compliance": {
    "GDPR": { "status": "partial", "gaps": ["..."] },
    "SOC2": { "status": "ok" }
  },
  "blockers": [],
  "score": 0.8
}
```

## Взаимодействие со state

Owner: `state.security`. Читает `state.idea`, `state.architecture`.

## Зависимости

- MCP tools для policy / vuln DB.
- Каталог регуляторных шаблонов в репозитории конфигурации.

## Конфигурация

| Параметр | Значение |
|----------|----------|
| `frameworks` | `["GDPR", "SOC2"]` |
| `threat_model` | `"STRIDE"` |
| `min_mitigations_per_threat` | 1 |

## Безопасность

- Может писать только в `state.security`.
- Имеет право заблокировать дальнейший ход workflow при обнаружении hard‑blocker (`blockers != []`).

## Наблюдаемость

- Метрики: `threats_found`, `compliance_gaps`, `blockers_raised`.
- Лог: полный отчёт с маскированием чувствительных данных.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| Нет архитектуры | вернуть ошибку Reflector‑у. |
| Hard‑blocker | перевести сессию в `failed` или потребовать одобрение пользователя. |

## Точки расширения

- Подключение SAST/DAST/SCA‑тулов через MCP.
- Домены: финтех, медтех, госсектор — со специализированными чек‑листами.

## Связанные модули

- [agents.md](agents.md), [agents-architect.md](agents-architect.md), [validator.md](validator.md), [mcp-gateway.md](mcp-gateway.md).
