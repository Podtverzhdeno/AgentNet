"""Orchestrator node.

Acts as the entry point: classifies the intent (mock implementation —
keyword based), assigns a session id and seeds the iteration counters.

See ``docs/modules/orchestrator.md`` for the full spec.
"""

from __future__ import annotations

import uuid

from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)

_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "audit": ("audit", "аудит", "compliance", "комплаенс", "gdpr"),
    "design": ("design", "архитектур", "проектиров", "platform", "платформ"),
    "analysis": ("анализ", "research", "исследов", "оцени"),
}


def classify_intent(idea: str) -> str:
    text = idea.lower()
    for intent, keywords in _INTENT_KEYWORDS.items():
        if any(k in text for k in keywords):
            return intent
    return "custom"


def orchestrator_node(state: GraphState) -> dict[str, object]:
    idea = state.get("idea", "")
    session_id = state.get("session_id") or f"sess-{uuid.uuid4().hex[:12]}"
    intent = classify_intent(idea)
    iteration = state.get("iteration") or 1
    max_iterations = state.get("max_iterations") or 3
    score_threshold = state.get("score_threshold") or 0.8
    mode = state.get("mode") or "auto"

    log.info(
        "orchestrator.start",
        session_id=session_id,
        intent=intent,
        iteration=iteration,
        idea_preview=idea[:80],
    )

    return {
        "session_id": session_id,
        "intent": intent,
        "iteration": iteration,
        "max_iterations": max_iterations,
        "score_threshold": score_threshold,
        "mode": mode,
    }


__all__ = ["classify_intent", "orchestrator_node"]
