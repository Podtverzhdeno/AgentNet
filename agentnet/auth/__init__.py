"""Tenant resolution from HTTP requests (Phase 3.A).

Exposes a tiny :class:`TenantResolver` Protocol plus three concrete
implementations:

* :class:`StaticTenantResolver` — always returns the same tenant. Used
  in tests and as the default in single‑tenant deployments.
* :class:`HeaderTenantResolver` — reads ``X-Tenant-Id`` from the
  request. Useful behind a trusted gateway that already authenticated
  the caller.
* :class:`BearerTokenTenantResolver` — maps ``Authorization: Bearer
  <token>`` against an in‑memory token table. Phase 3 placeholder for a
  real OIDC integration.

The factory :func:`make_tenant_resolver` is wired into the FastAPI
:func:`agentnet.api.make_app` lifespan.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from ..state import DEFAULT_TENANT


@runtime_checkable
class TenantResolver(Protocol):
    def resolve(self, headers: Mapping[str, str]) -> str: ...


class StaticTenantResolver:
    """Always return the configured tenant (default ``"default"``)."""

    def __init__(self, tenant: str = DEFAULT_TENANT) -> None:
        self.tenant = tenant

    def resolve(self, headers: Mapping[str, str]) -> str:  # noqa: ARG002 — interface parity
        return self.tenant


class HeaderTenantResolver:
    """Read ``X-Tenant-Id`` (case‑insensitive) from headers."""

    def __init__(self, *, header_name: str = "X-Tenant-Id", default: str = DEFAULT_TENANT) -> None:
        self._key = header_name.lower()
        self._default = default

    def resolve(self, headers: Mapping[str, str]) -> str:
        for k, v in headers.items():
            if k.lower() == self._key and v:
                return v
        return self._default


class BearerTokenTenantResolver:
    """Map ``Authorization: Bearer <token>`` against an in‑memory table.

    Returns *default* when no header is present; raises
    :class:`PermissionError` when the token is unknown.
    """

    def __init__(
        self,
        token_to_tenant: Mapping[str, str],
        *,
        default: str = DEFAULT_TENANT,
        require_token: bool = False,
    ) -> None:
        self._tokens = dict(token_to_tenant)
        self._default = default
        self._require = require_token

    def resolve(self, headers: Mapping[str, str]) -> str:
        auth = ""
        for k, v in headers.items():
            if k.lower() == "authorization":
                auth = v
                break
        if not auth:
            if self._require:
                raise PermissionError("missing Authorization header")
            return self._default
        scheme, _, token = auth.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise PermissionError("invalid Authorization scheme")
        tenant = self._tokens.get(token.strip())
        if tenant is None:
            raise PermissionError("unknown bearer token")
        return tenant


def make_tenant_resolver(
    *,
    tokens: Mapping[str, str] | None = None,
    static: str | None = None,
    require_token: bool = False,
) -> TenantResolver:
    """Pick a sensible resolver based on what's configured.

    Order:
    1. ``tokens`` provided → :class:`BearerTokenTenantResolver`.
    2. ``static`` provided → :class:`StaticTenantResolver`.
    3. otherwise → :class:`HeaderTenantResolver` (trusted‑proxy mode).
    """

    if tokens:
        return BearerTokenTenantResolver(tokens, require_token=require_token)
    if static is not None:
        return StaticTenantResolver(static)
    return HeaderTenantResolver()


__all__ = [
    "BearerTokenTenantResolver",
    "HeaderTenantResolver",
    "StaticTenantResolver",
    "TenantResolver",
    "make_tenant_resolver",
]
