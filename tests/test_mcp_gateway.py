"""Tests for the real MCP Gateway (Phase 2.B).

Covers:

* YAML config validation (refs + duplicates).
* In-process transport happy-path + RBAC denial.
* Rate limiting and audit-on-denial.
* Approval-gated tools.
* HTTP transport via ``pytest-httpx``.
* JSON-Lines audit log persisted to disk.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import yaml

from agentnet.mcp_gateway import (
    AuditLog,
    GatewayConfig,
    HTTPTransport,
    InProcessTransport,
    MCPGateway,
    SlidingWindowRateLimiter,
    ToolApprovalRequiredError,
    ToolNotAuthorizedError,
    ToolNotFoundError,
    ToolRateLimitedError,
    load_config,
)
from agentnet.mcp_gateway.audit import ToolCall

# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def _basic_config(audit_log: Path) -> dict:
    return {
        "audit_log": str(audit_log),
        "default_rate_limit_rpm": 60,
        "backends": {
            "local": {"transport": "in_process"},
            "remote": {"transport": "http", "base_url": "https://mcp.example.com"},
        },
        "tools": {
            "echo": {"backend": "local"},
            "publish": {"backend": "local", "require_approval": True},
            "fetch": {"backend": "remote", "timeout_seconds": 5},
            "throttled": {"backend": "local", "rate_limit_rpm": 2},
        },
        "roles": {
            "ResearchAgent": {"allow": ["echo", "fetch"]},
            "AnalyticsAgent": {
                "allow": ["echo", "throttled"],
                "approval": ["publish"],
            },
        },
    }


# --------------------------------------------------------------------------- #
# Config                                                                      #
# --------------------------------------------------------------------------- #


def test_load_config_round_trip(tmp_path: Path) -> None:
    cfg_path = _write_yaml(tmp_path / "tools.yaml", _basic_config(tmp_path / "audit.jsonl"))
    cfg = load_config(cfg_path)
    assert isinstance(cfg, GatewayConfig)
    assert cfg.tools["fetch"].backend == "remote"
    assert cfg.roles["AnalyticsAgent"].approval == ["publish"]
    assert cfg.backends["remote"].base_url == "https://mcp.example.com"


def test_config_rejects_unknown_backend(tmp_path: Path) -> None:
    data = _basic_config(tmp_path / "audit.jsonl")
    data["tools"]["echo"]["backend"] = "missing"
    cfg_path = _write_yaml(tmp_path / "tools.yaml", data)
    with pytest.raises(ValueError, match="unknown backend"):
        load_config(cfg_path)


def test_config_rejects_unknown_tool_in_role(tmp_path: Path) -> None:
    data = _basic_config(tmp_path / "audit.jsonl")
    data["roles"]["ResearchAgent"]["allow"].append("ghost")
    cfg_path = _write_yaml(tmp_path / "tools.yaml", data)
    with pytest.raises(ValueError, match="unknown tool 'ghost'"):
        load_config(cfg_path)


def test_config_rejects_tool_in_both_allow_and_approval(tmp_path: Path) -> None:
    data = _basic_config(tmp_path / "audit.jsonl")
    data["roles"]["AnalyticsAgent"]["allow"].append("publish")
    cfg_path = _write_yaml(tmp_path / "tools.yaml", data)
    with pytest.raises(ValueError, match="appear in both allow and approval"):
        load_config(cfg_path)


def test_config_http_backend_requires_base_url(tmp_path: Path) -> None:
    data = _basic_config(tmp_path / "audit.jsonl")
    data["backends"]["remote"].pop("base_url")
    cfg_path = _write_yaml(tmp_path / "tools.yaml", data)
    with pytest.raises(ValueError, match="requires base_url"):
        load_config(cfg_path)


# --------------------------------------------------------------------------- #
# Rate limiter                                                                #
# --------------------------------------------------------------------------- #


def test_rate_limiter_allows_up_to_rpm() -> None:
    rl = SlidingWindowRateLimiter(rpm=3)
    assert rl.acquire("k", now=0)
    assert rl.acquire("k", now=1)
    assert rl.acquire("k", now=2)
    assert not rl.acquire("k", now=3)


def test_rate_limiter_window_expires() -> None:
    rl = SlidingWindowRateLimiter(rpm=2, window_seconds=10)
    assert rl.acquire("k", now=0)
    assert rl.acquire("k", now=5)
    assert not rl.acquire("k", now=9)
    # past the window
    assert rl.acquire("k", now=15)


# --------------------------------------------------------------------------- #
# Audit log                                                                   #
# --------------------------------------------------------------------------- #


def test_audit_log_writes_jsonl(tmp_path: Path) -> None:
    log_path = tmp_path / "audit.jsonl"
    log = AuditLog(path=log_path)
    log.record(
        ToolCall(
            tool="echo",
            role="ResearchAgent",
            params={"x": 1},
            duration_ms=2.0,
            success=True,
            result="hi",
        )
    )
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["tool"] == "echo"
    assert payload["success"] is True


# --------------------------------------------------------------------------- #
# Gateway: in-process                                                         #
# --------------------------------------------------------------------------- #


@pytest.fixture()
def gateway(tmp_path: Path) -> MCPGateway:
    cfg_path = _write_yaml(tmp_path / "tools.yaml", _basic_config(tmp_path / "audit.jsonl"))
    return MCPGateway.from_config(
        cfg_path,
        in_process_tools={
            "local": {
                "echo": lambda **kw: {"echo": kw},
                "publish": lambda **kw: {"published": kw},
                "throttled": lambda **kw: kw,
            }
        },
    )


def test_gateway_call_succeeds_for_allowed_role(gateway: MCPGateway) -> None:
    result = gateway.call(role="ResearchAgent", tool="echo", params={"x": 1})
    assert result == {"echo": {"x": 1}}
    last = gateway.audit.entries[-1]
    assert last.success is True
    assert last.role == "ResearchAgent"
    assert last.tool == "echo"


def test_gateway_unknown_tool(gateway: MCPGateway) -> None:
    with pytest.raises(ToolNotFoundError):
        gateway.call(role="ResearchAgent", tool="ghost")
    assert gateway.audit.entries[-1].error == "denied:tool_not_found"


def test_gateway_unauthorized_role(gateway: MCPGateway) -> None:
    with pytest.raises(ToolNotAuthorizedError):
        gateway.call(role="ResearchAgent", tool="publish")
    assert gateway.audit.entries[-1].error == "denied:not_authorized"


def test_gateway_approval_required(gateway: MCPGateway) -> None:
    with pytest.raises(ToolApprovalRequiredError):
        gateway.call(role="AnalyticsAgent", tool="publish", params={"x": 1})
    assert gateway.audit.entries[-1].error == "denied:approval_required"


def test_gateway_approval_rejected(gateway: MCPGateway) -> None:
    with pytest.raises(ToolApprovalRequiredError):
        gateway.call(
            role="AnalyticsAgent",
            tool="publish",
            params={"x": 1},
            approval_decision="reject",
        )
    assert gateway.audit.entries[-1].error == "denied:approval_rejected"


def test_gateway_approval_granted(gateway: MCPGateway) -> None:
    out = gateway.call(
        role="AnalyticsAgent",
        tool="publish",
        params={"x": 1},
        approval_decision="approve",
    )
    assert out == {"published": {"x": 1}}
    assert gateway.audit.entries[-1].success is True


def test_gateway_rate_limit(gateway: MCPGateway) -> None:
    gateway.call(role="AnalyticsAgent", tool="throttled", params={"i": 1})
    gateway.call(role="AnalyticsAgent", tool="throttled", params={"i": 2})
    with pytest.raises(ToolRateLimitedError):
        gateway.call(role="AnalyticsAgent", tool="throttled", params={"i": 3})
    assert gateway.audit.entries[-1].error == "denied:rate_limited"


def test_gateway_list_tools(gateway: MCPGateway) -> None:
    assert gateway.list_tools("ResearchAgent") == ["echo", "fetch"]
    assert gateway.list_tools("AnalyticsAgent") == ["echo", "publish", "throttled"]
    assert gateway.list_tools("Unknown") == []


def test_audit_log_persisted_to_disk(gateway: MCPGateway, tmp_path: Path) -> None:
    gateway.call(role="ResearchAgent", tool="echo", params={"hello": True})
    log_path = tmp_path / "audit.jsonl"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["tool"] == "echo"
    assert payload["role"] == "ResearchAgent"
    assert payload["success"] is True


# --------------------------------------------------------------------------- #
# Gateway: HTTP transport                                                     #
# --------------------------------------------------------------------------- #


def test_http_transport_round_trip(httpx_mock):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="POST",
        url="https://mcp.example.com/mcp/call",
        json={"status": "success", "result": {"hello": "world"}, "duration_ms": 5},
    )
    transport = HTTPTransport(base_url="https://mcp.example.com")
    out = transport.call("fetch", {"q": "hi"}, timeout=2.0)
    assert out == {"hello": "world"}


def test_gateway_http_transport_via_config(httpx_mock, tmp_path: Path):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="POST",
        url="https://mcp.example.com/mcp/call",
        json={"result": [1, 2, 3]},
    )
    cfg_path = _write_yaml(tmp_path / "tools.yaml", _basic_config(tmp_path / "audit.jsonl"))
    gateway = MCPGateway.from_config(cfg_path)
    out = gateway.call(role="ResearchAgent", tool="fetch", params={"q": "search"})
    assert out == [1, 2, 3]
    assert gateway.audit.entries[-1].tool == "fetch"
    assert gateway.audit.entries[-1].success is True


def test_gateway_http_5xx_is_audited_and_raised(httpx_mock, tmp_path: Path):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="POST",
        url="https://mcp.example.com/mcp/call",
        status_code=500,
        json={"error": "boom"},
    )
    cfg_path = _write_yaml(tmp_path / "tools.yaml", _basic_config(tmp_path / "audit.jsonl"))
    gateway = MCPGateway.from_config(cfg_path)
    with pytest.raises(httpx.HTTPStatusError):
        gateway.call(role="ResearchAgent", tool="fetch", params={"q": "x"})
    last = gateway.audit.entries[-1]
    assert last.success is False
    assert "500" in (last.error or "")


# --------------------------------------------------------------------------- #
# InProcessTransport directly                                                 #
# --------------------------------------------------------------------------- #


def test_in_process_transport_basic() -> None:
    t = InProcessTransport()
    t.register("add", lambda a, b: a + b)
    assert t.call("add", {"a": 1, "b": 2}, timeout=1.0) == 3
    assert t.has("add")
    with pytest.raises(KeyError):
        t.call("missing", {}, timeout=1.0)
