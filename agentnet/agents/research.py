"""Research Agent.

Default Phase 1 behaviour is deterministic so the test suite remains
reproducible without API keys. Phase 2.A adds an LLM‑driven variant via
:func:`make_research_node` — pass an :class:`agentnet.llm.LLMClient` to
opt in.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from ..llm import ChatMessage, LLMClient, MockLLMClient
from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a research analyst. Given a project idea, produce a JSON object "
    'with keys "questions" (list of strings), "findings" '
    '(list of {claim, confidence, sources}), "summary" (string), '
    'and "sources" (list of URLs). Respond with JSON only, no prose.'
)


def research_node(state: GraphState) -> dict[str, object]:
    """Deterministic Phase‑1 research output (no LLM)."""

    idea = state.get("idea", "")
    findings = [
        {
            "claim": f"Market for '{idea[:60]}' is growing.",
            "evidence": [{"source": "mock://kb/market", "snippet": "mock evidence"}],
            "confidence": 0.7,
        },
        {
            "claim": "There are at least 3 direct competitors.",
            "evidence": [{"source": "mock://web/competitors", "snippet": "mock evidence"}],
            "confidence": 0.8,
        },
    ]
    research = {
        "questions": ["Who is the target user?", "What is the moat?"],
        "findings": findings,
        "summary": f"Mock research summary for: {idea[:80]}",
        "sources": ["mock://kb/market", "mock://web/competitors"],
    }
    log.info(
        "research.run",
        session_id=state.get("session_id"),
        findings=len(findings),
        backend="mock",
    )
    return {"research": research}


def make_research_node(
    llm: LLMClient | None = None,
) -> Callable[[GraphState], dict[str, object]]:
    """Return a research node bound to *llm*.

    ``None`` or :class:`MockLLMClient` keeps the deterministic Phase‑1
    behaviour. Any other client triggers a real LLM call.
    """

    if llm is None or isinstance(llm, MockLLMClient):
        return research_node

    def _node(state: GraphState) -> dict[str, object]:
        idea = state.get("idea", "")
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(role="user", content=f"Idea: {idea}"),
        ]
        resp = llm.complete(messages)
        try:
            parsed = json.loads(resp.content)
        except json.JSONDecodeError:
            parsed = {
                "summary": resp.content,
                "questions": [],
                "findings": [],
                "sources": [],
            }
        log.info(
            "research.run",
            session_id=state.get("session_id"),
            backend=llm.model,
            findings=len(parsed.get("findings") or []),
        )
        return {"research": parsed}

    return _node


__all__ = ["make_research_node", "research_node"]
