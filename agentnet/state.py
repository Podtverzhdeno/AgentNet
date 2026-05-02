"""State schema for AgentNet.

Two complementary types live here:

* :class:`GraphState` — :class:`TypedDict` used by LangGraph at runtime. Every
  node receives it and returns a partial update (also a ``dict``).
* :class:`SessionRequest` / :class:`SessionResult` — Pydantic models used at
  the API/CLI boundary for input validation and structured output.

The :class:`GraphState` mirrors the schema documented in
``docs/STATE_MODEL.md``. Fields are all optional so that nodes can return
incremental updates and so that the model is easy to construct in tests.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

Mode = Literal["auto", "confirm-each-step", "manual"]


class PlanNode(TypedDict):
    """Single task in the DAG produced by the Planner."""

    id: int
    agent: str
    task: str
    deps: list[int]


class Plan(TypedDict):
    """DAG of tasks. Edges are encoded as ``deps`` on each node."""

    nodes: list[PlanNode]


class GraphState(TypedDict, total=False):
    """Runtime state object shared by all LangGraph nodes."""

    # input
    idea: str
    intent: str

    # plan
    plan: Plan
    tasks: list[dict[str, Any]]

    # worker outputs
    research: dict[str, Any]
    architecture: dict[str, Any]
    security: dict[str, Any]
    analytics: dict[str, Any]

    # iteration outputs
    result: dict[str, Any] | str
    score: float
    feedback: str
    issues: list[str]

    # meta
    iteration: int
    max_iterations: int
    score_threshold: float
    session_id: str
    mode: Mode


class SessionRequest(BaseModel):
    """Request payload for ``run_session`` / ``POST /api/session/start``."""

    task: str = Field(..., description="Idea or task description")
    mode: Mode = "auto"
    max_iterations: int = Field(3, ge=1, le=20)
    score_threshold: float = Field(0.8, ge=0.0, le=1.0)


class SessionResult(BaseModel):
    """Final, user-facing result of a session."""

    session_id: str
    iterations: int
    score: float
    result: dict[str, Any] | str | None = None
    feedback: str | None = None
    final_state: dict[str, Any]
