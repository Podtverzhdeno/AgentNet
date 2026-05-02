"""Declarative YAML configuration for :class:`agentnet.mcp_gateway.MCPGateway`.

A config defines three things:

* ``backends`` — how to talk to a tool. Either ``in_process`` (registry of
  Python callables) or ``http`` (a remote MCP server).
* ``tools`` — public tool name → backend + per-tool policy (timeout, rate
  limit, approval gate).
* ``roles`` — RBAC matrix: which tools each role can call, and which
  require explicit approval.

The Pydantic models below are also re-used to serialize the config back
out for ``agentnet mcp config-check``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class BackendConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport: Literal["in_process", "http"] = "in_process"
    base_url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float | None = None

    @model_validator(mode="after")
    def _http_requires_base_url(self) -> BackendConfig:
        if self.transport == "http" and not self.base_url:
            raise ValueError("backend with transport=http requires base_url")
        return self


class ToolConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend: str
    timeout_seconds: float | None = None
    rate_limit_rpm: int | None = None
    require_approval: bool = False

    @field_validator("rate_limit_rpm")
    @classmethod
    def _positive(cls, v: int | None) -> int | None:
        if v is not None and v <= 0:
            raise ValueError("rate_limit_rpm must be > 0")
        return v


class RoleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allow: list[str] = Field(default_factory=list)
    approval: list[str] = Field(default_factory=list)


class GatewayConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audit_log: str | None = None
    default_timeout_seconds: float = 30.0
    default_rate_limit_rpm: int = 60
    backends: dict[str, BackendConfig] = Field(default_factory=dict)
    tools: dict[str, ToolConfig] = Field(default_factory=dict)
    roles: dict[str, RoleConfig] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_refs(self) -> GatewayConfig:
        # tool.backend must reference a known backend
        for name, tool in self.tools.items():
            if tool.backend not in self.backends:
                raise ValueError(f"tool {name!r} references unknown backend {tool.backend!r}")
        # role.allow / role.approval must reference known tools
        for role_name, role in self.roles.items():
            for entry in (*role.allow, *role.approval):
                if entry not in self.tools:
                    raise ValueError(f"role {role_name!r} references unknown tool {entry!r}")
            duplicates = set(role.allow) & set(role.approval)
            if duplicates:
                raise ValueError(
                    f"role {role_name!r}: tool(s) {sorted(duplicates)!r} "
                    "appear in both allow and approval"
                )
        return self


def load_config(path: str | Path) -> GatewayConfig:
    """Load and validate a gateway YAML config from *path*."""

    raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(raw) or {}
    return GatewayConfig.model_validate(data)


__all__ = [
    "BackendConfig",
    "GatewayConfig",
    "RoleConfig",
    "ToolConfig",
    "load_config",
]
