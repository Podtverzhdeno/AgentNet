"""MCP Gateway — single trust boundary between agents and external tools.

Phase 2.B introduces a real :class:`MCPGateway` with YAML‑driven RBAC,
multi‑backend transports (in‑process and HTTP), per‑(role, tool) rate
limiting and a JSON‑Lines audit log.

The legacy :class:`MockMCPGateway` is preserved for the agent unit tests
that predated this work — it is now a thin convenience wrapper around
:class:`InProcessTransport` and :class:`AuditLog`.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from .audit import AuditLog, ToolCall
from .config import (
    BackendConfig,
    GatewayConfig,
    RoleConfig,
    ToolConfig,
    load_config,
)
from .gateway import (
    MCPGateway,
    ToolApprovalRequiredError,
    ToolNotAuthorizedError,
    ToolNotFoundError,
    ToolRateLimitedError,
    ToolTimeoutError,
)
from .ratelimit import SlidingWindowRateLimiter
from .transport import HTTPTransport, InProcessTransport, Transport


class MockMCPGateway:
    """In‑process gateway used in agent / orchestrator tests.

    Kept for backwards compatibility with Phase 1 tests. New code should
    construct a real :class:`MCPGateway` (typically via
    :meth:`MCPGateway.from_config`). This shim mimics the original
    ``rbac``/``audit`` properties and supports the same
    ``allow``/``register``/``call`` operations.
    """

    def __init__(self) -> None:
        self.rbac: dict[str, list[str]] = {}
        self._tools: dict[str, Callable[..., Any]] = {}
        self._audit = AuditLog(path=None)

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    def allow(self, role: str, *tools: str) -> None:
        self.rbac.setdefault(role, []).extend(tools)

    def call(self, *, role: str, tool: str, params: dict[str, Any] | None = None) -> Any:
        params = dict(params or {})
        if tool not in self._tools:
            self._audit.record(
                ToolCall(
                    tool=tool,
                    role=role,
                    params=params,
                    duration_ms=0.0,
                    success=False,
                    error="denied:tool_not_found",
                )
            )
            raise ToolNotFoundError(tool)
        if tool not in self.rbac.get(role, []):
            self._audit.record(
                ToolCall(
                    tool=tool,
                    role=role,
                    params=params,
                    duration_ms=0.0,
                    success=False,
                    error="denied:not_authorized",
                )
            )
            raise ToolNotAuthorizedError(f"role {role!r} cannot call {tool!r}")
        started = time.perf_counter()
        try:
            result = self._tools[tool](**params)
        except Exception as exc:  # noqa: BLE001 — re-raise after audit
            duration_ms = (time.perf_counter() - started) * 1000
            self._audit.record(
                ToolCall(
                    tool=tool,
                    role=role,
                    params=params,
                    duration_ms=duration_ms,
                    success=False,
                    error=str(exc),
                )
            )
            raise
        duration_ms = (time.perf_counter() - started) * 1000
        self._audit.record(
            ToolCall(
                tool=tool,
                role=role,
                params=params,
                duration_ms=duration_ms,
                success=True,
                result=result,
            )
        )
        return result

    @property
    def audit(self) -> list[ToolCall]:
        return self._audit.entries


__all__ = [
    "AuditLog",
    "BackendConfig",
    "GatewayConfig",
    "HTTPTransport",
    "InProcessTransport",
    "MCPGateway",
    "MockMCPGateway",
    "RoleConfig",
    "SlidingWindowRateLimiter",
    "ToolApprovalRequiredError",
    "ToolCall",
    "ToolConfig",
    "ToolNotAuthorizedError",
    "ToolNotFoundError",
    "ToolRateLimitedError",
    "ToolTimeoutError",
    "Transport",
    "load_config",
]
