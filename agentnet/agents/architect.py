"""Architect Agent.

Default behaviour is the Phase‑1 deterministic mock. Pass an LLM client
to :func:`make_architect_node` to switch to a JSON‑producing LLM call.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from ..llm import ChatMessage, LLMClient, MockLLMClient
from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are a senior software architect. Given an idea and any prior "
    "research, produce a JSON object with keys 'modules' (list of "
    "{name, responsibilities, tech}), 'diagrams', 'stack_decisions' and "
    "'non_functional'. Respond with JSON only."
)


def architect_node(state: GraphState) -> dict[str, object]:
    modules = [
        {"name": "Orchestrator", "responsibilities": ["entry point"], "tech": "LangGraph"},
        {"name": "Planner", "responsibilities": ["build DAG"], "tech": "LangGraph + LLM"},
        {"name": "WorkerAgents", "responsibilities": ["execute tasks"], "tech": "LangChain"},
        {"name": "MCP Gateway", "responsibilities": ["tool RBAC"], "tech": "FastMCP"},
    ]
    architecture = {
        "modules": modules,
        "diagrams": [{"kind": "mermaid", "uri": "mock://artifact/diagram.md"}],
        "stack_decisions": [
            {"choice": "Postgres", "rationale": "stateful sessions + checkpoints"},
            {"choice": "Qdrant", "rationale": "vector memory for RAG"},
        ],
        "non_functional": {
            "latency_p95_seconds": 90,
            "scale": "horizontal via K8s HPA",
        },
    }
    log.info(
        "architect.run",
        session_id=state.get("session_id"),
        modules=len(modules),
        backend="mock",
    )
    return {"architecture": architecture}


def make_architect_node(
    llm: LLMClient | None = None,
) -> Callable[[GraphState], dict[str, object]]:
    """Architect node factory; falls back to mock when no real LLM."""

    if llm is None or isinstance(llm, MockLLMClient):
        return architect_node

    def _node(state: GraphState) -> dict[str, object]:
        idea = state.get("idea", "")
        research = state.get("research")
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"Idea: {idea}\nResearch: {json.dumps(research, default=str)[:2000]}",
            ),
        ]
        resp = llm.complete(messages)
        try:
            parsed = json.loads(resp.content)
        except json.JSONDecodeError:
            parsed = {"modules": [], "diagrams": [], "stack_decisions": [], "summary": resp.content}
        log.info(
            "architect.run",
            session_id=state.get("session_id"),
            backend=llm.model,
            modules=len(parsed.get("modules") or []),
        )
        return {"architecture": parsed}

    return _node


__all__ = ["architect_node", "make_architect_node"]
