"""Transports used by :class:`agentnet.mcp_gateway.MCPGateway`.

Two implementations:

* :class:`InProcessTransport` — a registry of plain Python callables. Used
  for tests and local development; the original ``MockMCPGateway`` is now
  a thin wrapper around this.
* :class:`HTTPTransport` — POSTs ``{tool, params}`` to ``{base_url}/mcp/call``
  per ``docs/API_CONTRACTS.md`` and returns the ``result`` field. Implemented
  with :mod:`httpx` so we can stub it in tests via ``pytest-httpx``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import httpx


class Transport(Protocol):
    """Wire the gateway up to a downstream tool implementation."""

    def call(
        self,
        tool: str,
        params: dict[str, Any],
        *,
        timeout: float,
        headers: dict[str, str] | None = None,
    ) -> Any:
        """Run *tool* with *params* and return the raw result."""
        ...


class InProcessTransport:
    """A registry of locally-callable tools — no network I/O.

    Use :meth:`register` to add tools and :meth:`call` for execution.
    Timeouts are advisory (Python can't safely abort sync code), so we
    pass them through but don't enforce.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, fn: Callable[..., Any]) -> None:
        self._tools[name] = fn

    def has(self, name: str) -> bool:
        return name in self._tools

    def call(
        self,
        tool: str,
        params: dict[str, Any],
        *,
        timeout: float,  # noqa: ARG002 — see docstring
        headers: dict[str, str] | None = None,  # noqa: ARG002
    ) -> Any:
        if tool not in self._tools:
            raise KeyError(tool)
        return self._tools[tool](**params)


class HTTPTransport:
    """Talks to a remote MCP Gateway / FastMCP server over HTTP.

    Wire format mirrors ``docs/API_CONTRACTS.md``::

        POST {base_url}/mcp/call
        { "tool": "...", "params": {...} }

        200 OK
        { "status": "success", "result": ..., "duration_ms": 142 }

    Errors are raised as :class:`httpx.HTTPStatusError` for >=400 and
    :class:`httpx.TimeoutException` on timeout.
    """

    def __init__(
        self,
        base_url: str,
        *,
        default_headers: dict[str, str] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._default_headers = dict(default_headers or {})
        self._client = client or httpx.Client()
        self._owns_client = client is None

    def call(
        self,
        tool: str,
        params: dict[str, Any],
        *,
        timeout: float,
        headers: dict[str, str] | None = None,
    ) -> Any:
        merged: dict[str, str] = {**self._default_headers, **(headers or {})}
        resp = self._client.post(
            f"{self.base_url}/mcp/call",
            json={"tool": tool, "params": params},
            headers=merged,
            timeout=timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if isinstance(body, dict) and "result" in body:
            return body["result"]
        return body

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


__all__ = [
    "HTTPTransport",
    "InProcessTransport",
    "Transport",
]
