# UI

## Назначение

Веб‑дашборд для пользователя и оператора: запуск сессий, наблюдение за работой агентов, ручное одобрение действий, доступ к артефактам и метрикам.

## Ответственности

- Отображать список сессий, их статусы, прогресс по DAG.
- Стримить промежуточные обновления (SSE / WebSocket).
- Визуализировать DAG плана и текущую позицию выполнения.
- Управлять human‑in‑the‑loop: approve / reject шагов, ввод уточнений.
- Показывать reasoning агентов (стрим токенов).
- Доступ к артефактам (документы, диаграммы, отчёты валидации).
- Управление skills (просмотр, регистрация, deprecate).
- Просмотр метрик и трейсов сессии.

## Стек

- Frontend: React / Next.js + TypeScript.
- State: react‑query + zustand.
- Визуализация: react‑flow для DAG, mermaid для диаграмм.
- Auth: OIDC через корпоративный IdP.
- API: REST + SSE; для long‑running — websockets.

## Основные экраны

| Экран | Содержимое |
|-------|------------|
| `Sessions` | Список сессий, фильтры, поиск. |
| `Session detail` | DAG, стрим, артефакты, history итераций. |
| `Approve` | Карточки шагов, требующих ручного одобрения. |
| `Skills` | Каталог, регистрация, метрики. |
| `Memory` | Поиск по long‑term памяти. |
| `Observability` | Метрики, трейсы, ошибки. |
| `Settings` | Режим, квоты, пользовательские предпочтения. |

## Безопасность

- Все запросы — с валидным OIDC‑токеном.
- CSRF protection.
- CSP, strict‑transport‑security, разделение фронт‑домена и API‑домена.
- Per‑tenant изоляция данных.

## Конфигурация

| Параметр | Значение |
|----------|----------|
| `api_base_url` | в env / runtime config |
| `streaming_protocol` | `sse` |
| `default_mode` | `auto` |

## Наблюдаемость

- Frontend telemetry: web vitals, error reporting.
- Server‑side: usual access/error логи.

## Failure modes

| Ошибка | Поведение |
|--------|-----------|
| Поток обновлений разорван | автоматический reconnect, восстановление состояния. |
| API недоступно | toast + локальная очередь действий (где безопасно). |
| Невалидный токен | редирект на login. |

## Точки расширения

- Темизация per‑tenant.
- Embed‑виджеты для внешних порталов.
- Plugin slots для кастомных визуализаций (например, schema diagrams).

## Связанные модули

- [orchestrator.md](orchestrator.md), [observability.md](observability.md), [skills.md](skills.md), [cli.md](cli.md).
