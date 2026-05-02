"""Tests for the Planner node."""

from __future__ import annotations

from agentnet.planner import planner_node


def test_planner_emits_default_plan() -> None:
    update = planner_node({"idea": "any", "iteration": 1})
    plan = update["plan"]
    assert isinstance(plan, dict)
    nodes = plan["nodes"]
    assert len(nodes) == 4
    agents = {n["agent"] for n in nodes}
    assert agents == {"ResearchAgent", "ArchitectAgent", "SecurityAgent", "AnalyticsAgent"}


def test_planner_preserves_existing_plan() -> None:
    existing = {"nodes": [{"id": 99, "agent": "Custom", "task": "Stub", "deps": []}]}
    update = planner_node({"idea": "x", "plan": existing, "iteration": 2})
    assert update["plan"] is existing
