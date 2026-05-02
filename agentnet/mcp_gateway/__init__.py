"""MCP Gateway — mock client.

The real Gateway (FastMCP / Prefect Horizon) handles RBAC, audit and
secret resolution (see ``docs/modules/mcp-gateway.md``). The mock here
provides a :class:`MockMCPGateway` that registers and dispatches local
Python callables, so worker agents can be developed and tested without a
live network.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    tool: str
    params: dict[str, Any]
    duration_ms: float
    success: bool
    result: Any = None
    error: str | None = None


class ToolNotAuthorizedError(RuntimeError):
    """Raised when a role is not allowed to call the requested tool."""


class ToolNotFoundError(RuntimeError):
    """Raised when the tool isn't registered with the gateway."""


@dataclass
class MockMCPGateway:
    """In-process MCP gateway used in tests and the local CLI."""

    rbac: dict[str, list[str]] = field(default_factory=dict)
    _tools: dict[str, Callable[..., Any]] = field(default_factory=dict)
    _audit: list[ToolCall] = field(default_factory=list)

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    def allow(self, role: str, *tools: str) -> None:
        self.rbac.setdefault(role, []).extend(tools)

    def call(self, *, role: str, tool: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}
        if tool not in self._tools:
            raise ToolNotFoundError(tool)
        if tool not in self.rbac.get(role, []):
            raise ToolNotAuthorizedError(f"role {role!r} cannot call {tool!r}")
        started = time.perf_counter()
        try:
            result = self._tools[tool](**params)
            duration_ms = (time.perf_counter() - started) * 1000
            self._audit.append(
                ToolCall(
                    tool=tool,
                    params=params,
                    duration_ms=duration_ms,
                    success=True,
                    result=result,
                )
            )
            return result
        except Exception as exc:  # noqa: BLE001 — we intentionally capture all
            duration_ms = (time.perf_counter() - started) * 1000
            self._audit.append(
                ToolCall(
                    tool=tool,
                    params=params,
                    duration_ms=duration_ms,
                    success=False,
                    error=str(exc),
                )
            )
            raise

    @property
    def audit(self) -> list[ToolCall]:
        return list(self._audit)


__all__ = [
    "MockMCPGateway",
    "ToolCall",
    "ToolNotAuthorizedError",
    "ToolNotFoundError",
]
