"""PII‑aware :class:`agentnet.llm.LLMClient` decorator."""

from __future__ import annotations

from ..llm import ChatMessage, LLMClient, LLMResponse
from .redactor import Redactor


class ScrubbedLLMClient:
    """Wrap an :class:`LLMClient` so prompts (and optionally responses) run through a :class:`Redactor`.

    By default we scrub **prompts only** — that's what keeps secrets on
    the box. Set ``scrub_response=True`` if you also want to redact PII
    that the model regurgitates (useful when the response is later
    persisted in long‑term memory).
    """

    def __init__(
        self,
        inner: LLMClient,
        *,
        redactor: Redactor | None = None,
        scrub_prompt: bool = True,
        scrub_response: bool = False,
    ) -> None:
        self._inner = inner
        self._redactor = redactor or Redactor()
        self._scrub_prompt = scrub_prompt
        self._scrub_response = scrub_response

    @property
    def model(self) -> str:
        return self._inner.model

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> LLMResponse:
        if self._scrub_prompt:
            messages = [
                ChatMessage(role=m.role, content=self._redactor.redact(m.content)) for m in messages
            ]
        response = self._inner.complete(messages, max_tokens=max_tokens, temperature=temperature)
        if self._scrub_response:
            return LLMResponse(
                content=self._redactor.redact(response.content),
                model=response.model,
                usage=response.usage,
                raw=response.raw,
            )
        return response


__all__ = ["ScrubbedLLMClient"]
