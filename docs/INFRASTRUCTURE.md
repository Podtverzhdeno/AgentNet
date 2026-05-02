# Infrastructure

## Целевая среда

- Kubernetes (on‑prem или managed: EKS / GKE / AKS / корпоративный кластер).
- Service mesh опционально (Istio / Linkerd) для mTLS, retries, circuit breakers.
- Container registry с проверкой сигнатур (Cosign).
- CI/CD: GitHub Actions / Jenkins / ArgoCD.

## Развёртывание модулей

| Модуль | Тип нагрузки | Реплицируемость |
|--------|--------------|-----------------|
| Orchestrator API | Deployment | Stateless, горизонтально |
| Planner / Validator / Reflector | Deployment | Stateless, горизонтально |
| Worker Agents | Deployment / Job | Pool на роль; горизонтально |
| MCP Gateway | Deployment | Stateless, HA |
| Memory (vector DB) | StatefulSet / managed | Шардирование |
| Memory (Redis short‑term) | StatefulSet / managed | HA пары |
| Sandbox runtime | DaemonSet / KubeVirt / Firecracker host | Per‑node |
| UI | Deployment + CDN | Stateless |
| Scheduler | Deployment + leader election | 1 active |
| Observability | Helm‑чарты Prometheus / Grafana / Loki / OTEL | — |

## Масштабирование

- **Horizontal Pod Autoscaling** по CPU / queue depth для агентов.
- **Очередь задач** (Redis / NATS / SQS) между Orchestrator и Worker pool.
- **Шардирование** long‑term memory по тенантам.
- **Контейнеры на узлах с GPU** — отдельный node pool с taint `gpu=true`, `nvidia.com/gpu` selector.
- **Sandbox host pool** — отдельные узлы с включённым KVM/Firecracker.

## Сетевая модель

- mTLS внутри кластера.
- Egress только через прокси с allowlist.
- MCP Gateway — единственный путь к внешним сервисам.
- NetworkPolicy запрещает agent‑pod → agent‑pod обмен напрямую.

## Стек технологий

| Слой | Выбор |
|------|-------|
| Оркестрация workflow | LangChain / LangGraph |
| MCP | FastMCP + Prefect Horizon |
| Агенты | LangChain Agents / собственная обёртка |
| Short‑term memory | Redis / Postgres |
| Long‑term memory | Qdrant / Pinecone / Weaviate |
| RDBMS | PostgreSQL |
| Object storage | S3 / MinIO |
| Sandbox | Docker, gVisor, Kata, Firecracker |
| Auth | Keycloak / corporate IdP, OIDC |
| Secrets | HashiCorp Vault / Cloud KMS |
| Mонитор. | Prometheus, Grafana, Loki, OpenTelemetry, LangSmith |
| CI/CD | GitHub Actions + ArgoCD |
| IaC | Terraform / Pulumi + Helm |

## Конфигурация

- Все значения — через Helm values + ConfigMap + Vault.
- Конфиг разделён на:
  - `platform` (общий стек),
  - `tenants` (изоляция по тенанту),
  - `agents/<name>` (per‑agent параметры и квоты),
  - `tools/<name>` (per‑tool RBAC и лимиты).

## Тенант‑изоляция

- Namespace per tenant.
- DB role per tenant.
- Vault path per tenant.
- Префикс ключей в long‑term memory `tenant:<id>:...`.
- Audit‑логи разделены по тенанту.

## DR / Backup

- Postgres + Redis: PITR backup, репликация в DR‑регион.
- Vector DB: snapshot ежедневно.
- Audit‑бакет: WORM, repl. cross‑region.
- DR runbook: RPO 1h, RTO 4h (стартовая цель — настраивается).

## Стоимость и пределы (предварительно)

Замеры сделаются после MVP; ориентиры:

| Метрика | Цель |
|---------|------|
| p95 latency сессии (3 итерации) | ≤ 90 секунд |
| Параллельные сессии на кластер | 100+ |
| Стоимость одной сессии | определяется по миксу LLM моделей |
