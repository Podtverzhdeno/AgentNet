"""Tests for the Validator node."""

from __future__ import annotations

from agentnet.validator import validator_node


def _full_state(iteration: int) -> dict[str, object]:
    return {
        "idea": "x",
        "iteration": iteration,
        "score_threshold": 0.8,
        "research": {"findings": []},
        "architecture": {"modules": []},
        "security": {"threats": [], "blockers": []},
        "analytics": {"kpis": []},
        "result": {"completeness": 1.0},
    }


def test_validator_score_grows_with_iterations() -> None:
    first = validator_node(_full_state(1))
    second = validator_node(_full_state(2))
    assert isinstance(first["score"], float)
    assert isinstance(second["score"], float)
    assert second["score"] > first["score"]


def test_validator_first_iteration_below_threshold() -> None:
    update = validator_node(_full_state(1))
    assert update["score"] < 0.8


def test_validator_second_iteration_passes() -> None:
    update = validator_node(_full_state(2))
    assert update["score"] >= 0.8
    assert "passed" in str(update["feedback"]).lower()


def test_validator_collects_missing_section_issues() -> None:
    state = _full_state(1)
    state.pop("research")
    update = validator_node(state)
    assert any("research" in issue for issue in update["issues"])  # type: ignore[operator]
