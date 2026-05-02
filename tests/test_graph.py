"""End-to-end tests for the LangGraph workflow."""

from __future__ import annotations

from agentnet import SessionRequest, build_graph, run_session


def test_graph_compiles() -> None:
    graph = build_graph()
    assert graph is not None
    nodes = list(graph.get_graph().nodes)
    for expected in (
        "orchestrator",
        "planner",
        "research",
        "architect",
        "security",
        "analytics",
        "aggregate",
        "validate",
        "reflect",
    ):
        assert expected in nodes, f"missing node: {expected}"


def test_run_session_finishes_after_one_reflection() -> None:
    request = SessionRequest(task="Спроектировать аналитическую систему", max_iterations=3)
    result = run_session(request)
    assert result.iterations == 2  # iter 1 fails (0.7), iter 2 passes (0.9)
    assert result.score >= 0.8
    assert isinstance(result.result, dict)
    assert "sections" in result.result


def test_run_session_respects_max_iterations() -> None:
    request = SessionRequest(task="any", max_iterations=1, score_threshold=0.99)
    result = run_session(request)
    assert result.iterations == 1
    assert result.score < 0.99


def test_run_session_writes_all_sections() -> None:
    result = run_session(SessionRequest(task="design analytics platform"))
    assert isinstance(result.result, dict)
    sections = result.result["sections"]
    assert set(sections) == {"research", "architecture", "security", "analytics"}
    for section in sections.values():
        assert section
