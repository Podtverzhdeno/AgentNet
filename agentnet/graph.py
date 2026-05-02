"""LangGraph wiring for the AgentNet skeleton.

The graph mirrors ``docs/RUNTIME_WORKFLOW.md``:

* ``orchestrator`` seeds the session,
* ``planner`` builds the DAG,
* ``research`` / ``architect`` / ``security`` / ``analytics`` fan out in parallel,
* ``aggregate`` joins them,
* ``validate`` scores the result,
* ``reflect`` increments the iteration and routes back to the planner when
  the score is below threshold (and the iteration budget hasn't been spent).

Phase 2.C adds optional checkpointing: pass a ``checkpointer`` to
:func:`build_graph` (or a ``checkpointer_uri`` to :func:`run_session`) and
the orchestrator stores the state of every node transition so that
sessions can be inspected, resumed, or replayed later.
"""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from .agents import (
    make_analytics_node,
    make_architect_node,
    make_research_node,
    make_security_node,
)
from .aggregator import aggregator_node
from .llm import LLMClient, make_llm_client
from .observability import get_logger
from .orchestrator import orchestrator_node
from .persistence import make_checkpointer
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


def build_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    *,
    llm: LLMClient | None = None,
) -> Any:
    """Compile the LangGraph state machine.

    ``checkpointer`` enables persistence; ``llm`` plumbs a real LLM
    client into the worker agents (Phase 2.A). When ``llm`` is ``None``
    or a :class:`MockLLMClient`, every agent uses its deterministic
    Phase‑1 mock body so existing tests stay reproducible without API
    keys.
    """

    g: StateGraph[GraphState, Any, GraphState, GraphState] = StateGraph(GraphState)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("planner", planner_node)
    g.add_node("research", make_research_node(llm))  # type: ignore[arg-type]
    g.add_node("architect", make_architect_node(llm))  # type: ignore[arg-type]
    g.add_node("security", make_security_node(llm))  # type: ignore[arg-type]
    g.add_node("analytics", make_analytics_node(llm))  # type: ignore[arg-type]
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

    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


def run_session(
    request: SessionRequest,
    *,
    thread_id: str | None = None,
    checkpointer_uri: str | None = None,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    llm: LLMClient | None = None,
    llm_spec: str | None = None,
) -> SessionResult:
    """Run a session synchronously and return a :class:`SessionResult`.

    Parameters
    ----------
    request:
        Validated user request (idea, mode, thresholds).
    thread_id:
        Optional LangGraph thread identifier. When ``None`` a fresh one is
        generated and returned via :attr:`SessionResult.session_id`.
    checkpointer_uri:
        URI for :func:`agentnet.persistence.make_checkpointer`. Ignored
        when ``checkpointer`` is provided directly.
    checkpointer:
        Pre-built checkpointer. Useful in tests.
    llm:
        Pre-built LLM client. Mutually exclusive with ``llm_spec``.
    llm_spec:
        ``provider[:model]`` string parsed by
        :func:`agentnet.llm.make_llm_client`. ``None`` falls back to
        ``$AGENTNET_LLM`` and finally to ``MockLLMClient``.
    """

    if checkpointer is None and checkpointer_uri is not None:
        checkpointer = make_checkpointer(checkpointer_uri)
    if llm is None:
        llm = make_llm_client(llm_spec)

    graph = build_graph(checkpointer=checkpointer, llm=llm)

    thread_id = thread_id or f"sess-{uuid.uuid4().hex[:12]}"
    initial: GraphState = {
        "idea": request.task,
        "iteration": 1,
        "max_iterations": request.max_iterations,
        "score_threshold": request.score_threshold,
        "mode": request.mode,
        "session_id": thread_id,
    }

    invoke_kwargs: dict[str, Any] = {}
    if checkpointer is not None:
        invoke_kwargs["config"] = {"configurable": {"thread_id": thread_id}}

    log.info(
        "session.start",
        thread_id=thread_id,
        idea_preview=request.task[:80],
        mode=request.mode,
        persisted=checkpointer is not None,
    )
    final_state: dict[str, Any] = graph.invoke(initial, **invoke_kwargs)
    log.info(
        "session.end",
        thread_id=thread_id,
        iterations=final_state.get("iteration"),
        score=final_state.get("score"),
    )
    return SessionResult(
        session_id=str(final_state.get("session_id", thread_id)),
        iterations=int(final_state.get("iteration", 1)),
        score=float(final_state.get("score", 0.0)),
        result=final_state.get("result"),
        feedback=final_state.get("feedback"),
        final_state=final_state,
    )


def get_session_state(
    thread_id: str, checkpointer: BaseCheckpointSaver[Any]
) -> dict[str, Any] | None:
    """Return the latest persisted state for ``thread_id`` or ``None``."""

    from langchain_core.runnables import RunnableConfig

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    tup = checkpointer.get_tuple(config)
    if tup is None:
        return None
    state = tup.checkpoint.get("channel_values", {})
    return dict(state)


__all__ = ["build_graph", "get_session_state", "run_session"]
