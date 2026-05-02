"""Pluggable LLM clients (Phase 2.A).

The platform talks to LLMs through a single :class:`LLMClient` Protocol.
Three concrete adapters are shipped:

* :class:`AnthropicLLMClient` — POST ``/v1/messages`` (Anthropic SDK
  compatible wire format).
* :class:`OpenAILLMClient` — POST ``/v1/chat/completions``.
* :class:`OllamaLLMClient` — POST ``/api/chat`` against a local Ollama
  daemon.

For tests and CI we ship :class:`MockLLMClient`, a deterministic stub
that doesn't touch the network. Worker agents pick a client through
:func:`make_llm_client` (which honours ``AGENTNET_LLM`` env var); when no
provider is configured, agents fall back to their original Phase 1 mock
behaviour so existing tests stay reproducible.
"""

from __future__ import annotations

from .client import (
    ChatMessage,
    LLMClient,
    LLMResponse,
    MockLLMClient,
)
from .factory import make_llm_client, parse_llm_spec
from .providers import AnthropicLLMClient, OllamaLLMClient, OpenAILLMClient

__all__ = [
    "AnthropicLLMClient",
    "ChatMessage",
    "LLMClient",
    "LLMResponse",
    "MockLLMClient",
    "OllamaLLMClient",
    "OpenAILLMClient",
    "make_llm_client",
    "parse_llm_spec",
]
