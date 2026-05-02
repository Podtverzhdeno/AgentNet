"""LangGraph wiring for the AgentNet Phase 1 skeleton.

The graph mirrors ``docs/RUNTIME_WORKFLOW.md``:

* ``orchestrator`` seeds the session,
* ``planner`` builds the DAG,
* ``research`` / ``architect`` / ``security`` / ``analytics`` fan out in parallel,
* ``aggregate`` joins them,
* ``validate`` scores the result,
* ``reflect`` increments the iteration and routes back to the planner when
  the score is below threshold (and the iteration budget hasn't been spent).
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from .agents import (
    analytics_node,
    architect_node,
    research_node,
    security_node,
)
from .aggregator import aggregator_node
from .observability import get_logger
from .orchestrator import orchestrator_node
from .planner import planner_node
from .reflector import reflector_node
from .state import GraphState, SessionRequest, SessionResult
from .validator import validator_node

log = get_logger(__name__)


def _route_after_validate(state: GraphState) -> str:
    score = state.get("score", 0.0)
    iteration = state.get("iteration", 1)
    threshold = state.get("score_threshold", 0.8)
    max_iter = state.get("max_iterations", 3)
    if score >= threshold or iteration >= max_iter:
        return "end"
    return "reflect"


def build_graph() -> Any:
    """Compile the LangGraph state machine and return the compiled graph."""

    g: StateGraph[GraphState, Any, GraphState, GraphState] = StateGraph(GraphState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("planner", planner_node)
    g.add_node("research", research_node)
    g.add_node("architect", architect_node)
    g.add_node("security", security_node)
    g.add_node("analytics", analytics_node)
    g.add_node("aggregate", aggregator_node)
    g.add_node("validate", validator_node)
    g.add_node("reflect", reflector_node)

    g.add_edge(START, "orchestrator")
    g.add_edge("orchestrator", "planner")

    # fan-out from planner to all worker agents
    for worker in ("research", "architect", "security", "analytics"):
        g.add_edge("planner", worker)
        g.add_edge(worker, "aggregate")

    g.add_edge("aggregate", "validate")
    g.add_conditional_edges(
        "validate",
        _route_after_validate,
        {"reflect": "reflect", "end": END},
    )
    g.add_edge("reflect", "planner")

    return g.compile()


def run_session(request: SessionRequest) -> SessionResult:
    """Run a session synchronously and return a :class:`SessionResult`."""

    graph = build_graph()
    initial: GraphState = {
        "idea": request.task,
        "iteration": 1,
        "max_iterations": request.max_iterations,
        "score_threshold": request.score_threshold,
        "mode": request.mode,
    }
    log.info("session.start", idea_preview=request.task[:80], mode=request.mode)
    final_state: dict[str, Any] = graph.invoke(initial)
    log.info(
        "session.end",
        iterations=final_state.get("iteration"),
        score=final_state.get("score"),
    )
    return SessionResult(
        session_id=str(final_state.get("session_id", "")),
        iterations=int(final_state.get("iteration", 1)),
        score=float(final_state.get("score", 0.0)),
        result=final_state.get("result"),
        feedback=final_state.get("feedback"),
        final_state=final_state,
    )


__all__ = ["build_graph", "run_session"]
