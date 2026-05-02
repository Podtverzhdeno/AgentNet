"""Tests for the Orchestrator node."""

from __future__ import annotations

from agentnet.orchestrator import classify_intent, orchestrator_node


def test_classify_intent_audit() -> None:
    assert classify_intent("Provide a security audit for our service") == "audit"
    assert classify_intent("Сделай аудит безопасности") == "audit"


def test_classify_intent_design() -> None:
    assert classify_intent("Спроектировать аналитическую платформу") == "design"


def test_classify_intent_analysis() -> None:
    assert classify_intent("Проведи анализ конкурентов") == "analysis"


def test_classify_intent_custom_fallback() -> None:
    assert classify_intent("Just say hi") == "custom"


def test_orchestrator_node_seeds_session() -> None:
    update = orchestrator_node({"idea": "Спроектировать систему"})
    assert update["intent"] == "design"
    assert isinstance(update["session_id"], str)
    assert update["iteration"] == 1
    assert update["max_iterations"] == 3
    assert update["score_threshold"] == 0.8


def test_orchestrator_node_preserves_session_id() -> None:
    update = orchestrator_node({"idea": "x", "session_id": "preset-id"})
    assert update["session_id"] == "preset-id"
