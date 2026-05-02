"""Factory: turn a string spec / env var into an :class:`LLMClient`.

Spec syntax::

    "mock"                                → MockLLMClient
    "anthropic"                           → AnthropicLLMClient (default model)
    "anthropic:claude-3-5-haiku-20241022" → AnthropicLLMClient with explicit model
    "openai"                              → OpenAILLMClient
    "openai:gpt-4o-mini"                  → OpenAILLMClient
    "ollama:llama3"                       → OllamaLLMClient

Lookup order when *spec* is ``None``:

1. ``AGENTNET_LLM`` env var.
2. Fall back to ``mock``.

API keys and base URLs come from env vars; CLI/API flags can override
them by passing the value directly. We never store keys in code.
"""

from __future__ import annotations

import os
from typing import NamedTuple

from .client import LLMClient, MockLLMClient
from .providers import AnthropicLLMClient, OllamaLLMClient, OpenAILLMClient


class LLMSpec(NamedTuple):
    provider: str
    model: str | None


def parse_llm_spec(spec: str | None) -> LLMSpec:
    """Parse a ``provider[:model]`` spec into :class:`LLMSpec`.

    Empty / ``None`` resolves to ``mock``.
    """

    if spec is None or not spec.strip():
        return LLMSpec(provider="mock", model=None)
    text = spec.strip()
    if ":" in text:
        provider, model = text.split(":", 1)
        return LLMSpec(provider=provider.lower(), model=model.strip() or None)
    return LLMSpec(provider=text.lower(), model=None)


def make_llm_client(
    spec: str | None = None,
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMClient:
    """Construct a client from *spec* (or env), with optional overrides.

    Resolution rules:

    * ``model`` arg overrides the model parsed out of ``spec``;
    * ``api_key`` arg overrides the provider-specific env var
      (``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY``);
    * ``base_url`` arg overrides the provider-specific default base URL
      (``OPENAI_BASE_URL`` / ``ANTHROPIC_BASE_URL`` / ``OLLAMA_BASE_URL``).
    """

    if spec is None or not spec.strip():
        spec = os.environ.get("AGENTNET_LLM")
    parsed = parse_llm_spec(spec)
    chosen_model = model or parsed.model

    if parsed.provider == "mock":
        return MockLLMClient(model=chosen_model or "mock")

    if parsed.provider == "anthropic":
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for the 'anthropic' provider")
        anthropic_base = base_url or os.environ.get("ANTHROPIC_BASE_URL")
        return AnthropicLLMClient(
            key,
            model=chosen_model or "claude-3-5-sonnet-20241022",
            base_url=anthropic_base or "https://api.anthropic.com",
        )

    if parsed.provider == "openai":
        key = api_key or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required for the 'openai' provider")
        openai_base = base_url or os.environ.get("OPENAI_BASE_URL")
        return OpenAILLMClient(
            key,
            model=chosen_model or "gpt-4o-mini",
            base_url=openai_base or "https://api.openai.com",
        )

    if parsed.provider == "ollama":
        ollama_base = base_url or os.environ.get("OLLAMA_BASE_URL")
        return OllamaLLMClient(
            model=chosen_model or "llama3",
            base_url=ollama_base or "http://127.0.0.1:11434",
        )

    raise ValueError(f"unsupported LLM provider {parsed.provider!r}")


__all__ = ["LLMSpec", "make_llm_client", "parse_llm_spec"]
