"""Validator node.

Scores the aggregated result. The mock score is deterministic and grows
with each iteration so that the reflection loop is exercised in tests:

* iteration 1 → 0.7 (below default threshold 0.8)
* iteration 2 → 0.9 (above the threshold, terminates)

It also collects ``issues`` from worker outputs (for example the threat
list from the Security Agent or any missing sections).

See ``docs/modules/validator.md``.
"""

from __future__ import annotations

from typing import Any

from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)


def validator_node(state: GraphState) -> dict[str, object]:
    iteration = state.get("iteration", 1)
    threshold = state.get("score_threshold", 0.8)

    completeness = _extract_completeness(state.get("result"))
    base = 0.5 + 0.2 * iteration
    score = round(min(1.0, base * completeness if completeness else base), 3)

    issues = _collect_issues(state)
    feedback = _build_feedback(score, threshold, issues, iteration)

    log.info(
        "validator.run",
        session_id=state.get("session_id"),
        iteration=iteration,
        score=score,
        issues_count=len(issues),
    )

    return {
        "score": score,
        "feedback": feedback,
        "issues": issues,
    }


def _extract_completeness(result: dict[str, Any] | str | None) -> float:
    if isinstance(result, dict):
        value = result.get("completeness")
        if isinstance(value, int | float):
            return float(value)
    return 1.0


def _collect_issues(state: GraphState) -> list[str]:
    issues: list[str] = []
    if not state.get("research"):
        issues.append("missing research section")
    if not state.get("architecture"):
        issues.append("missing architecture section")
    if not state.get("security"):
        issues.append("missing security section")
    if not state.get("analytics"):
        issues.append("missing analytics section")
    sec = state.get("security") or {}
    if isinstance(sec, dict):
        issues.extend(f"security: {t}" for t in sec.get("blockers", []))
    return issues


def _build_feedback(score: float, threshold: float, issues: list[str], iteration: int) -> str:
    if score >= threshold:
        return f"Validation passed at iteration {iteration} with score {score}."
    head = f"Score {score} below threshold {threshold} at iteration {iteration}."
    if issues:
        head += " Issues: " + "; ".join(issues[:5]) + "."
    return head


__all__ = ["validator_node"]
