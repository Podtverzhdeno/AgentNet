"""Research Agent (mock)."""

from __future__ import annotations

from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)


def research_node(state: GraphState) -> dict[str, object]:
    idea = state.get("idea", "")
    findings = [
        {
            "claim": f"Market for '{idea[:60]}' is growing.",
            "evidence": [{"source": "mock://kb/market", "snippet": "mock evidence"}],
            "confidence": 0.7,
        },
        {
            "claim": "There are at least 3 direct competitors.",
            "evidence": [{"source": "mock://web/competitors", "snippet": "mock evidence"}],
            "confidence": 0.8,
        },
    ]
    research = {
        "questions": ["Who is the target user?", "What is the moat?"],
        "findings": findings,
        "summary": f"Mock research summary for: {idea[:80]}",
        "sources": ["mock://kb/market", "mock://web/competitors"],
    }
    log.info(
        "research.run",
        session_id=state.get("session_id"),
        findings=len(findings),
    )
    return {"research": research}


__all__ = ["research_node"]
