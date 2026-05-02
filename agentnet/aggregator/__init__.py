"""Aggregator node.

Combines the four worker outputs (research / architecture / security /
analytics) into ``state.result``. The mock builds a structured dict with a
short summary block so that the Validator can score completeness.

See ``docs/modules/aggregator.md``.
"""

from __future__ import annotations

from typing import Any

from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)


def aggregator_node(state: GraphState) -> dict[str, object]:
    research = state.get("research") or {}
    architecture = state.get("architecture") or {}
    security = state.get("security") or {}
    analytics = state.get("analytics") or {}

    result: dict[str, Any] = {
        "summary": _summarise(state.get("idea", ""), research, architecture, security, analytics),
        "sections": {
            "research": research,
            "architecture": architecture,
            "security": security,
            "analytics": analytics,
        },
        "completeness": _completeness(research, architecture, security, analytics),
    }
    log.info(
        "aggregator.run",
        session_id=state.get("session_id"),
        completeness=result["completeness"],
    )
    return {"result": result}


def _summarise(
    idea: str,
    research: dict[str, Any],
    architecture: dict[str, Any],
    security: dict[str, Any],
    analytics: dict[str, Any],
) -> str:
    parts = [
        f"Idea: {idea[:120]}",
        f"Findings: {len(research.get('findings', []))}",
        f"Modules: {len(architecture.get('modules', []))}",
        f"Threats: {len(security.get('threats', []))}",
        f"KPIs: {len(analytics.get('kpis', []))}",
    ]
    return " | ".join(parts)


def _completeness(*sections: dict[str, Any]) -> float:
    filled = sum(1 for section in sections if section)
    return round(filled / max(len(sections), 1), 2)


__all__ = ["aggregator_node"]
