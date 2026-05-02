"""HTTP adapters for Anthropic / OpenAI / Ollama.

We deliberately avoid the vendor SDKs and call the REST endpoints
directly through :mod:`httpx`. That keeps deps thin and lets us stub the
wire format in tests with ``pytest-httpx``. If/when we need streaming or
tool-use, we can swap in the SDKs without changing :class:`LLMClient`.
"""

from __future__ import annotations

from typing import Any

import httpx

from .client import ChatMessage, LLMResponse


class _BaseHTTPClient:
    """Shared httpx plumbing — opens a client per adapter and closes it
    on :meth:`close` if we own the lifecycle."""

    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client()
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class AnthropicLLMClient(_BaseHTTPClient):
    """Anthropic ``/v1/messages`` adapter.

    Wire format reference: https://docs.anthropic.com/en/api/messages.
    System messages are sent via the top-level ``system`` field; user /
    assistant turns flow through ``messages``.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "claude-3-5-sonnet-20241022",
        base_url: str = "https://api.anthropic.com",
        anthropic_version: str = "2023-06-01",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(client=client)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.anthropic_version = anthropic_version

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        system_parts = [m.content for m in messages if m.role == "system"]
        chat = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        resp = self._client.post(
            f"{self.base_url}/v1/messages",
            json=payload,
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": self.anthropic_version,
                "content-type": "application/json",
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        body = resp.json()
        content_blocks = body.get("content") or []
        text = "".join(
            block.get("text", "") for block in content_blocks if block.get("type") == "text"
        )
        usage = body.get("usage") or {}
        return LLMResponse(
            content=text,
            model=body.get("model", self.model),
            usage={k: int(v) for k, v in usage.items() if isinstance(v, int)},
            raw=body,
        )


class OpenAILLMClient(_BaseHTTPClient):
    """OpenAI / OpenAI-compatible ``/v1/chat/completions`` adapter.

    Works with any provider that mirrors the OpenAI chat API (Together,
    Fireworks, vLLM, OpenRouter, …) — pass ``base_url`` to switch.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(client=client)
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        resp = self._client.post(
            f"{self.base_url}/v1/chat/completions",
            json=payload,
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        body = resp.json()
        choice = (body.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = message.get("content") or ""
        usage_in = body.get("usage") or {}
        return LLMResponse(
            content=text,
            model=body.get("model", self.model),
            usage={k: int(v) for k, v in usage_in.items() if isinstance(v, int)},
            raw=body,
        )


class OllamaLLMClient(_BaseHTTPClient):
    """Local Ollama ``/api/chat`` adapter (no streaming)."""

    def __init__(
        self,
        *,
        model: str = "llama3",
        base_url: str = "http://127.0.0.1:11434",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(client=client)
        self.model = model
        self.base_url = base_url.rstrip("/")

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        resp = self._client.post(
            f"{self.base_url}/api/chat",
            json=payload,
            timeout=60.0,
        )
        resp.raise_for_status()
        body = resp.json()
        message = body.get("message") or {}
        text = message.get("content") or ""
        usage = {
            "prompt_tokens": int(body.get("prompt_eval_count", 0) or 0),
            "completion_tokens": int(body.get("eval_count", 0) or 0),
        }
        return LLMResponse(
            content=text,
            model=body.get("model", self.model),
            usage=usage,
            raw=body,
        )


__all__ = ["AnthropicLLMClient", "OllamaLLMClient", "OpenAILLMClient"]
