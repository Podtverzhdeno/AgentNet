"""Tests for the in-process mock MCP gateway."""

from __future__ import annotations

import pytest

from agentnet.mcp_gateway import (
    MockMCPGateway,
    ToolNotAuthorizedError,
    ToolNotFoundError,
)


def test_authorized_tool_call_records_audit() -> None:
    gw = MockMCPGateway()
    gw.register("echo", lambda text: text)
    gw.allow("ResearchAgent", "echo")
    result = gw.call(role="ResearchAgent", tool="echo", params={"text": "hi"})
    assert result == "hi"
    assert len(gw.audit) == 1
    assert gw.audit[0].success is True


def test_unauthorized_tool_call_raises() -> None:
    gw = MockMCPGateway()
    gw.register("echo", lambda text: text)
    with pytest.raises(ToolNotAuthorizedError):
        gw.call(role="ResearchAgent", tool="echo", params={"text": "hi"})


def test_unknown_tool_raises() -> None:
    gw = MockMCPGateway()
    with pytest.raises(ToolNotFoundError):
        gw.call(role="ResearchAgent", tool="missing")


def test_tool_failure_recorded_in_audit() -> None:
    gw = MockMCPGateway()

    def failing(**_: object) -> None:
        raise RuntimeError("boom")

    gw.register("failing", failing)
    gw.allow("ResearchAgent", "failing")
    with pytest.raises(RuntimeError):
        gw.call(role="ResearchAgent", tool="failing")
    assert gw.audit[-1].success is False
    assert gw.audit[-1].error == "boom"
