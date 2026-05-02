"""Core LLM types: :class:`ChatMessage`, :class:`LLMResponse`, and the
:class:`LLMClient` Protocol implemented by every provider.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    """A single message in a chat-style prompt."""

    role: Role
    content: str


class LLMResponse(BaseModel):
    """Normalised response across all provider adapters."""

    content: str
    model: str
    usage: dict[str, int] = Field(default_factory=dict)
    raw: dict[str, Any] | None = None


@runtime_checkable
class LLMClient(Protocol):
    """Minimal interface every adapter implements.

    ``model`` is exposed as an attribute so observability layers can log
    it without poking provider-specific fields.
    """

    model: str

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse: ...


class MockLLMClient:
    """Deterministic in-process stub used in tests and as the default
    fallback when no real provider is configured.

    A custom ``responder`` lets tests inject canned answers; the default
    just echoes the last user message.
    """

    def __init__(
        self,
        *,
        model: str = "mock",
        responder: Callable[[list[ChatMessage]], str] | None = None,
    ) -> None:
        self.model = model
        self._responder = responder or _default_responder

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,  # noqa: ARG002 — interface parity
        temperature: float = 0.0,  # noqa: ARG002
    ) -> LLMResponse:
        content = self._responder(messages)
        return LLMResponse(content=content, model=self.model)


def _default_responder(messages: list[ChatMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "user":
            return f"mock:{msg.content[:120]}"
    return "mock:empty"


__all__ = ["ChatMessage", "LLMClient", "LLMResponse", "MockLLMClient"]
