"""Planner node.

Builds (or refines) a DAG of tasks for worker agents. The mock
implementation always emits the same four-node fan-out plan; on subsequent
iterations it preserves any feedback-driven additions injected by the
Reflector.

See ``docs/modules/planner.md``.
"""

from __future__ import annotations

from ..observability import get_logger
from ..state import GraphState, Plan, PlanNode

log = get_logger(__name__)


def _default_plan() -> Plan:
    nodes: list[PlanNode] = [
        {"id": 1, "agent": "ResearchAgent", "task": "MarketResearch", "deps": []},
        {"id": 2, "agent": "ArchitectAgent", "task": "DesignArchitecture", "deps": [1]},
        {"id": 3, "agent": "SecurityAgent", "task": "SecurityAudit", "deps": [2]},
        {"id": 4, "agent": "AnalyticsAgent", "task": "AnalyticsAndKPI", "deps": [2]},
    ]
    return {"nodes": nodes}


def planner_node(state: GraphState) -> dict[str, object]:
    iteration = state.get("iteration", 1)
    existing = state.get("plan")
    plan: Plan = existing if existing else _default_plan()
    log.info(
        "planner.run",
        session_id=state.get("session_id"),
        iteration=iteration,
        nodes=len(plan["nodes"]),
    )
    return {"plan": plan}


__all__ = ["planner_node"]
