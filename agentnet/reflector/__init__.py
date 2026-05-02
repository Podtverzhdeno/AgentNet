"""Reflector node.

Inspects the validator feedback, updates the plan (mock keeps the same
plan but bumps iteration) and returns control to the Planner. Real
implementation would re-prompt an LLM with the diff between current
and desired state.

See ``docs/modules/reflector.md``.
"""

from __future__ import annotations

from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)


def reflector_node(state: GraphState) -> dict[str, object]:
    iteration = state.get("iteration", 1)
    next_iteration = iteration + 1
    log.info(
        "reflector.run",
        session_id=state.get("session_id"),
        from_iteration=iteration,
        to_iteration=next_iteration,
        score=state.get("score"),
    )
    return {"iteration": next_iteration, "plan": state.get("plan")}


__all__ = ["reflector_node"]
