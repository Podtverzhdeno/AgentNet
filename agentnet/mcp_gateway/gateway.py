"""The :class:`MCPGateway` itself: RBAC + rate limit + audit + transport.

Worker agents and the orchestrator only ever talk to this class. They
never touch transports, audit logs or rate limiters directly. That keeps
the trust boundary clear: nothing outside ``mcp_gateway`` decides what
roles can call what.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

from .audit import AuditLog, ToolCall
from .config import GatewayConfig, load_config
from .ratelimit import SlidingWindowRateLimiter
from .transport import HTTPTransport, InProcessTransport, Transport


class ToolNotFoundError(LookupError):
    """The tool isn't declared in the gateway config."""


class ToolNotAuthorizedError(PermissionError):
    """The role isn't permitted to call this tool."""


class ToolApprovalRequiredError(PermissionError):
    """The tool requires explicit approval and none was supplied (or it was rejected)."""


class ToolRateLimitedError(RuntimeError):
    """Per-(role, tool) RPM was exceeded."""


class ToolTimeoutError(TimeoutError):
    """Downstream transport timed out."""


# A short, audit-safe preview of a tool result. We never persist the full
# payload because results can include PII or secrets — a real PII guard
# lands in Phase 3.
_AUDIT_PREVIEW_LEN = 200


def _preview(value: Any) -> Any:
    if isinstance(value, str):
        return value if len(value) <= _AUDIT_PREVIEW_LEN else value[:_AUDIT_PREVIEW_LEN] + "…"
    if isinstance(value, list | tuple) and len(value) > 10:
        return list(value[:10]) + ["…"]
    if isinstance(value, dict) and len(value) > 10:
        return {k: value[k] for k in list(value)[:10]}
    return value


class MCPGateway:
    """Real gateway used by agents in production-ish flows.

    The gateway is constructed with a validated :class:`GatewayConfig`
    and a mapping of backend name → :class:`Transport`. Use
    :meth:`from_config` for the typical YAML-driven path; pass transports
    directly when you want to inject :class:`InProcessTransport` for
    tests.
    """

    def __init__(
        self,
        config: GatewayConfig,
        transports: dict[str, Transport],
        *,
        audit: AuditLog | None = None,
    ) -> None:
        for name in config.backends:
            if name not in transports:
                raise ValueError(f"missing transport for backend {name!r}")
        self.config = config
        self.transports = transports
        self.audit = audit or AuditLog(path=config.audit_log)
        self._rate_limiters: dict[str, SlidingWindowRateLimiter] = {}
        for tool_name, tool in config.tools.items():
            rpm = tool.rate_limit_rpm or config.default_rate_limit_rpm
            self._rate_limiters[tool_name] = SlidingWindowRateLimiter(rpm=rpm)

    # ------------------------------------------------------------------ #
    # Construction                                                       #
    # ------------------------------------------------------------------ #

    @classmethod
    def from_config(
        cls,
        path: str | Path,
        *,
        in_process_tools: dict[str, dict[str, Any]] | None = None,
        http_clients: dict[str, httpx.Client] | None = None,
    ) -> MCPGateway:
        """Build a gateway from a YAML config.

        ``in_process_tools`` lets the caller seed an in-process backend
        with concrete callables. The dict shape is::

            {"backend_name": {"tool_name": fn, ...}, ...}

        ``http_clients`` lets tests inject an :class:`httpx.Client` so
        ``pytest-httpx`` can stub responses.
        """

        config = load_config(path)
        transports: dict[str, Transport] = {}
        in_process_tools = in_process_tools or {}
        http_clients = http_clients or {}
        for name, backend in config.backends.items():
            if backend.transport == "in_process":
                t = InProcessTransport()
                for tool_name, fn in (in_process_tools.get(name) or {}).items():
                    t.register(tool_name, fn)
                transports[name] = t
            elif backend.transport == "http":
                assert backend.base_url is not None  # validated by Pydantic
                transports[name] = HTTPTransport(
                    base_url=backend.base_url,
                    default_headers=backend.headers,
                    client=http_clients.get(name),
                )
            else:  # pragma: no cover — guarded by Pydantic Literal
                raise ValueError(f"unsupported transport {backend.transport!r}")
        return cls(config, transports)

    # ------------------------------------------------------------------ #
    # Public API                                                         #
    # ------------------------------------------------------------------ #

    def list_tools(self, role: str) -> list[str]:
        rcfg = self.config.roles.get(role)
        if rcfg is None:
            return []
        return sorted({*rcfg.allow, *rcfg.approval})

    def call(
        self,
        *,
        role: str,
        tool: str,
        params: dict[str, Any] | None = None,
        approval_decision: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Invoke *tool* on behalf of *role*.

        Order of checks:

        1. Tool exists in config.
        2. Role can call it (``allow`` or ``approval`` list).
        3. If gated, ``approval_decision`` must be ``"approve"``.
        4. Rate limit (per ``role:tool``).
        5. Resolve transport, run with timeout.
        6. Audit success/failure.
        """

        params = dict(params or {})
        tool_cfg = self.config.tools.get(tool)
        if tool_cfg is None:
            self._audit_denied(role, tool, params, "tool_not_found")
            raise ToolNotFoundError(tool)

        role_cfg = self.config.roles.get(role)
        in_allow = role_cfg is not None and tool in role_cfg.allow
        in_approval = role_cfg is not None and tool in role_cfg.approval
        if not in_allow and not in_approval:
            self._audit_denied(role, tool, params, "not_authorized")
            raise ToolNotAuthorizedError(f"role {role!r} cannot call {tool!r}")

        gated = in_approval or tool_cfg.require_approval
        if gated and approval_decision != "approve":
            reason = "approval_rejected" if approval_decision == "reject" else "approval_required"
            self._audit_denied(role, tool, params, reason)
            raise ToolApprovalRequiredError(
                f"tool {tool!r} requires explicit approval (got {approval_decision!r})"
            )

        if not self._rate_limiters[tool].acquire(f"{role}:{tool}"):
            self._audit_denied(role, tool, params, "rate_limited")
            raise ToolRateLimitedError(f"rate limit hit for {role!r} on {tool!r}")

        timeout = (
            tool_cfg.timeout_seconds
            or self.config.backends[tool_cfg.backend].timeout_seconds
            or self.config.default_timeout_seconds
        )
        transport = self.transports[tool_cfg.backend]
        started = time.perf_counter()
        try:
            result = transport.call(tool, params, timeout=timeout, headers=headers)
        except httpx.TimeoutException as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            self.audit.record(
                ToolCall(
                    tool=tool,
                    role=role,
                    params=params,
                    duration_ms=duration_ms,
                    success=False,
                    error=f"timeout: {exc}",
                )
            )
            raise ToolTimeoutError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 — propagate after audit
            duration_ms = (time.perf_counter() - started) * 1000
            self.audit.record(
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
        self.audit.record(
            ToolCall(
                tool=tool,
                role=role,
                params=params,
                duration_ms=duration_ms,
                success=True,
                result=_preview(result),
            )
        )
        return result

    # ------------------------------------------------------------------ #
    # Internals                                                          #
    # ------------------------------------------------------------------ #

    def _audit_denied(self, role: str, tool: str, params: dict[str, Any], reason: str) -> None:
        self.audit.record(
            ToolCall(
                tool=tool,
                role=role,
                params=params,
                duration_ms=0.0,
                success=False,
                error=f"denied:{reason}",
            )
        )


__all__ = [
    "MCPGateway",
    "ToolApprovalRequiredError",
    "ToolNotAuthorizedError",
    "ToolNotFoundError",
    "ToolRateLimitedError",
    "ToolTimeoutError",
]
