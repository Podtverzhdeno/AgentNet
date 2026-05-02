"""Security Agent.

Default Phase‑1 mock; :func:`make_security_node` returns an
LLM‑driven node when given a real :class:`LLMClient`.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from ..llm import ChatMessage, LLMClient, MockLLMClient
from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a security architect. Produce a JSON object with keys "
    "'threats' (list of {category, asset, risk, mitigation}), "
    "'compliance' (object), 'blockers' (list), and 'score' (0..1). "
    "Respond with JSON only."
)


def security_node(state: GraphState) -> dict[str, object]:
    threats = [
        {
            "category": "Spoofing",
            "asset": "Orchestrator API",
            "risk": "medium",
            "mitigation": "OIDC + mTLS",
        },
        {
            "category": "Tampering",
            "asset": "state.plan",
            "risk": "low",
            "mitigation": "checkpointed durable execution",
        },
    ]
    compliance = {
        "GDPR": {"status": "partial", "gaps": ["formal DPIA pending"]},
        "SOC2": {"status": "ok"},
    }
    security = {
        "threats": threats,
        "compliance": compliance,
        "blockers": [],
        "score": 0.85,
    }
    log.info(
        "security.run",
        session_id=state.get("session_id"),
        threats=len(threats),
        backend="mock",
    )
    return {"security": security}


def make_security_node(
    llm: LLMClient | None = None,
) -> Callable[[GraphState], dict[str, object]]:
    """Security node factory."""

    if llm is None or isinstance(llm, MockLLMClient):
        return security_node

    def _node(state: GraphState) -> dict[str, object]:
        idea = state.get("idea", "")
        ctx = {
            "research": state.get("research"),
            "architecture": state.get("architecture"),
        }
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"Idea: {idea}\nContext: {json.dumps(ctx, default=str)[:2000]}",
            ),
        ]
        resp = llm.complete(messages)
        try:
            parsed = json.loads(resp.content)
        except json.JSONDecodeError:
            parsed = {"threats": [], "compliance": {}, "blockers": [], "score": 0.0}
        log.info(
            "security.run",
            session_id=state.get("session_id"),
            backend=llm.model,
            threats=len(parsed.get("threats") or []),
        )
        return {"security": parsed}

    return _node


__all__ = ["make_security_node", "security_node"]
