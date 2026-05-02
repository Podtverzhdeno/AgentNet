# Sandbox

## Назначение

Изолированная среда исполнения каждого агента и каждого фрагмента сгенерированного кода. Гарантирует, что компрометация агента не приведёт к доступу к чужим данным или к инфраструктуре платформы.

## Ответственности

- Запуск процесса агента в изолированной среде с ограниченными правами.
- Ограничение CPU / RAM / disk / сети.
- FS — только разрешённые тома (rw scratch + ro общие ресурсы).
- Network — только через прокси / allowlist.
- Управление жизненным циклом контейнера/microVM (start/stop/kill).
- Чистка артефактов после завершения сессии.

## Профили

| Профиль | Технология | Когда использовать |
|---------|-----------|--------------------|
| `lite` | Docker | Простые stateless агенты (Planner, Validator). |
| `standard` | Docker + gVisor | По умолчанию для worker‑агентов. |
| `hardened` | Kata / Firecracker | Code‑exec, ненадёжный input, чувствительные тулы. |
| `air-gapped` | Firecracker + полный network‑off | Анализ ненадёжных артефактов / malware. |

## Контракт

```yaml
profile: standard
limits:
  cpu: "1000m"
  memory: "2Gi"
  ephemeral-storage: "5Gi"
  pids: 256
network:
  egress_allowlist:
    - "internal-mcp-gateway:443"
fs:
  scratch: "/work"      # rw, временный
  shared:  "/data:ro"   # ro, монтируется по запросу
seccomp: "default"
apparmor: "default"
no_new_privs: true
read_only_root: true
```

## Реализация

- На K8s: PodSecurityContext, LimitRange, NetworkPolicy.
- gVisor: runtime class `gvisor`.
- Kata / Firecracker: runtime class `kata-clh` / dedicated node pool.
- Per‑pod ServiceAccount с capability‑токенами.

## Безопасность

- `read_only_root_filesystem: true` всегда.
- `runAsNonRoot: true`, `runAsUser >= 1000`.
- `allowPrivilegeEscalation: false`.
- Удалённые секреты — через Vault sidecar / projected token, не через env vars.
- Egress controls на уровне service mesh + NetworkPolicy.

## Наблюдаемость

- Метрики: `sandbox_starts`, `sandbox_kills`, `sandbox_oom`, `sandbox_runtime_p95`.
- Логи: stdout/stderr контейнера в централизованный лог‑стор.
- Trace: span на жизнь sandbox‑контейнера.

## Failure modes & повторы

| Ошибка | Поведение |
|--------|-----------|
| OOM kill | retry с увеличенным memory (до лимита). |
| Network deny | лог + ошибка агенту. |
| Sandbox crash | start заново, до 2 попыток. |
| Превышение runtime | kill, escalate в Reflector. |

## Точки расширения

- Поддержка GPU‑sandbox (для ML‑агентов).
- Custom runtime classes per‑tenant (политика безопасности).
- Snapshot и rollback состояния sandbox для отладки.

## Связанные модули

- [agents.md](agents.md), [mcp-gateway.md](mcp-gateway.md), [../SECURITY.md](../SECURITY.md), [../INFRASTRUCTURE.md](../INFRASTRUCTURE.md).
