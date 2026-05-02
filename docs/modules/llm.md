# LLM Clients

## Назначение

Все обращения worker‑агентов к LLM проходят через единый интерфейс
`LLMClient`. Это позволяет:

- легко менять провайдера (Anthropic / OpenAI / Ollama / любой
  OpenAI‑совместимый endpoint) без правок в самих агентах;
- иметь детерминированный `MockLLMClient` для тестов и CI без API‑ключей;
- логировать `model` и `usage` в structlog/observability‑слое
  единообразно.

## Контракт

```python
class LLMClient(Protocol):
    model: str

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse: ...
```

`ChatMessage(role: "system" | "user" | "assistant", content: str)`,
`LLMResponse(content: str, model: str, usage: dict[str, int], raw: dict | None)`.

## Реализации (Phase 2.A)

| Класс                  | Endpoint                              | Auth env var          |
|------------------------|----------------------------------------|-----------------------|
| `MockLLMClient`        | (in‑process)                           | —                     |
| `AnthropicLLMClient`   | `POST /v1/messages`                    | `ANTHROPIC_API_KEY`   |
| `OpenAILLMClient`      | `POST /v1/chat/completions`            | `OPENAI_API_KEY`      |
| `OllamaLLMClient`      | `POST /api/chat` на `OLLAMA_BASE_URL`  | —                     |

`AnthropicLLMClient`/`OpenAILLMClient` дополнительно принимают `base_url`,
что позволяет ходить через прокси‑совместимые сервисы (Together,
Fireworks, OpenRouter, vLLM).

## Factory

```python
from agentnet.llm import make_llm_client

# из переменной окружения AGENTNET_LLM:
client = make_llm_client()                 # → MockLLMClient если ничего не задано
client = make_llm_client("mock")
client = make_llm_client("openai:gpt-4o-mini")
client = make_llm_client(
    "anthropic:claude-3-5-haiku-20241022",
    api_key="sk-ant-...",                 # перебивает env
    base_url="https://gateway.example/v1", # перебивает env
)
```

## Подключение к графу

```python
from agentnet.graph import build_graph
from agentnet.llm import make_llm_client

graph = build_graph(llm=make_llm_client("openai:gpt-4o-mini"))
# или
graph = build_graph()  # без LLM — детерминированный mock
```

Из CLI:

```bash
agentnet session start "design a fintech app" --llm openai:gpt-4o-mini
```

Из HTTP API:

```python
from agentnet.api import make_app
app = make_app(llm_spec="anthropic:claude-3-5-haiku-20241022")
```

## Что делают агенты при включённом LLM

`make_<role>_node(llm)` отправляет такие сообщения:

- system: коротенький role‑prompt («ты исследователь / архитектор / …»),
- user: идея + сериализованный slice предыдущих результатов
  (research → architect, research+architecture → security, и т.д.).

Ожидается JSON‑ответ. Если парсинг не удался — мы кладём ответ как
`summary` и оставляем структурированные поля пустыми, чтобы граф не
ломался.

## Что **не** входит в Phase 2.A

- streaming / tool‑use API провайдеров — Phase 3;
- прокидывание `LLMClient` в Planner/Validator/Reflector (сейчас они
  всё ещё детерминированы) — Phase 2.A.2;
- вторая попытка / fallback‑цепочки между провайдерами — Phase 3;
- бюджетные лимиты на токены / стоимость — Phase 3.

## Связанные модули

- [agents.md](agents.md) — где именно используется `LLMClient`.
- [observability.md](observability.md) — поля `backend` / `model` в логах
  агентов.
- [../SECURITY.md](../SECURITY.md) — где живут ключи и как они
  подменяются прокси Vault‑ом в Phase 3.
