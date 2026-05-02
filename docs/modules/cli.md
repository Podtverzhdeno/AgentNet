# CLI

## Назначение

Терминальный интерфейс для разработчиков, аналитиков и для самих агентов («terminal‑first» интерфейс по аналогии с LangSmith CLI).

## Ответственности

- Работа с сессиями: запуск, статус, отмена, approve.
- Работа со skills: list / register / deprecate.
- Работа с памятью: search / store / delete.
- Локальная разработка: запуск LangGraph dev‑сервера, тестирование графов.
- Скриптинг для CI/CD.

## Команды (черновик)

```text
agentnet session start "Спроектировать аналитическую платформу" --mode auto
agentnet session status XYZ123
agentnet session stream XYZ123
agentnet session approve XYZ123 --step 12
agentnet session cancel XYZ123

agentnet skill list --tag security
agentnet skill register ./skills/security_audit.yaml
agentnet skill deprecate skill.security_audit.v1

agentnet memory search "GDPR audit checklist" --top-k 5
agentnet memory delete <id>

agentnet dev serve   # локально поднять LangGraph dev сервер
agentnet dev replay  # воспроизвести записанную сессию
```

## Флаги для human‑in‑the‑loop

| Флаг | Действие |
|------|---------|
| `--auto` | пропускать все одобрения. |
| `--confirm-each-step` | подтверждать каждый шаг. |
| `--manual` | пользователь вручную запускает каждый узел. |
| `--yolo` | отключить мягкие проверки (записывается в audit). |

## Реализация

- Python (Typer / Click) или TypeScript (oclif).
- Конфиг — `~/.agentnet/config.yaml`.
- Auth — OIDC device flow + refresh tokens в keychain.

## Безопасность

- Токены — в OS keychain, не в plain text.
- `--yolo` пишется в audit‑лог.
- Запрет CLI на запуск вне корпоративной сети без VPN (опционально).

## Наблюдаемость

- CLI отправляет client‑side telemetry (опционально, opt‑in).
- Лог команд — локально и (опционально) в централизованный сток.

## Failure modes

| Ошибка | Поведение |
|--------|-----------|
| Network down | offline‑режим (просмотр кэша). |
| Token expired | auto refresh; иначе — re‑login. |
| API 5xx | retry с backoff, отчёт пользователю. |

## Точки расширения

- Plugins для кастомных команд.
- Shell‑completions (bash/zsh/fish).
- Интеграция с git hooks для автоматических аудитов идей в PR.

## Связанные модули

- [orchestrator.md](orchestrator.md), [skills.md](skills.md), [memory.md](memory.md), [ui.md](ui.md).
