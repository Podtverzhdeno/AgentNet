"""Analytics Agent (mock)."""

from __future__ import annotations

from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)


def analytics_node(state: GraphState) -> dict[str, object]:
    kpis = [
        {
            "name": "Active sessions",
            "definition": "Sessions per day",
            "sql": "SELECT COUNT(*) FROM sessions WHERE created_at >= now() - interval '1 day'",
        },
        {
            "name": "Average score",
            "definition": "Mean validator score across sessions",
            "sql": "SELECT AVG(score) FROM sessions",
        },
    ]
    analytics = {
        "kpis": kpis,
        "dashboards": [{"name": "Platform overview", "panels": [k["name"] for k in kpis]}],
        "forecast": {"method": "naive", "horizon_months": 6, "result": {}},
        "roi": {"horizon_months": 12, "estimate": "TBD"},
    }
    log.info(
        "analytics.run",
        session_id=state.get("session_id"),
        kpis=len(kpis),
    )
    return {"analytics": analytics}


__all__ = ["analytics_node"]
