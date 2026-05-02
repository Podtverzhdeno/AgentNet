"""Security Agent (mock)."""

from __future__ import annotations

from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)


def security_node(state: GraphState) -> dict[str, object]:
    threats = [
        {
            "category": "Spoofing",
            "asset": "Orchestrator API",
            "risk": "medium",
            "mitigation": "OIDC + mTLS",
        },
        {
            "category": "Tampering",
            "asset": "state.plan",
            "risk": "low",
            "mitigation": "checkpointed durable execution",
        },
    ]
    compliance = {
        "GDPR": {"status": "partial", "gaps": ["formal DPIA pending"]},
        "SOC2": {"status": "ok"},
    }
    security = {
        "threats": threats,
        "compliance": compliance,
        "blockers": [],
        "score": 0.85,
    }
    log.info(
        "security.run",
        session_id=state.get("session_id"),
        threats=len(threats),
    )
    return {"security": security}


__all__ = ["security_node"]
