"""Analytics Agent.

Default Phase‑1 mock; :func:`make_analytics_node` returns an
LLM‑driven node when given a real :class:`LLMClient`.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from ..llm import ChatMessage, LLMClient, MockLLMClient
from ..observability import get_logger
from ..state import GraphState

log = get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are an analytics lead. Produce a JSON object with keys "
    "'kpis' (list of {name, definition, sql}), 'dashboards', "
    "'forecast' and 'roi'. Respond with JSON only."
)


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
        backend="mock",
    )
    return {"analytics": analytics}


def make_analytics_node(
    llm: LLMClient | None = None,
) -> Callable[[GraphState], dict[str, object]]:
    """Analytics node factory."""

    if llm is None or isinstance(llm, MockLLMClient):
        return analytics_node

    def _node(state: GraphState) -> dict[str, object]:
        idea = state.get("idea", "")
        ctx = {
            "research": state.get("research"),
            "architecture": state.get("architecture"),
        }
        messages = [
            ChatMessage(role="system", content=_SYSTEM_PROMPT),
            ChatMessage(
                role="user",
                content=f"Idea: {idea}\nContext: {json.dumps(ctx, default=str)[:2000]}",
            ),
        ]
        resp = llm.complete(messages)
        try:
            parsed = json.loads(resp.content)
        except json.JSONDecodeError:
            parsed = {"kpis": [], "dashboards": [], "forecast": {}, "roi": {}}
        log.info(
            "analytics.run",
            session_id=state.get("session_id"),
            backend=llm.model,
            kpis=len(parsed.get("kpis") or []),
        )
        return {"analytics": parsed}

    return _node


__all__ = ["analytics_node", "make_analytics_node"]
