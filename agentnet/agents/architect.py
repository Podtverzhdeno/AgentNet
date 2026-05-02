"""Architect Agent (mock)."""

from __future__ import annotations

from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)


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
    )
    return {"architecture": architecture}


__all__ = ["architect_node"]
