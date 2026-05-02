"""Tests for Phase 3.A — per‑tenant isolation across CLI, persistence and HTTP API."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from agentnet.api import make_app
from agentnet.auth import (
    BearerTokenTenantResolver,
    HeaderTenantResolver,
    StaticTenantResolver,
    TenantResolver,
    make_tenant_resolver,
)
from agentnet.persistence import (
    get_thread_tenant,
    list_thread_ids,
    list_thread_ids_for_tenant,
)
from agentnet.state import SessionRequest

# --------------------------------------------------------------------------- #
# Tenant resolvers                                                             #
# --------------------------------------------------------------------------- #


def test_static_resolver_ignores_headers() -> None:
    r = StaticTenantResolver("acme")
    assert r.resolve({"X-Tenant-Id": "evil"}) == "acme"


def test_header_resolver_reads_x_tenant_id_case_insensitive() -> None:
    r = HeaderTenantResolver()
    assert r.resolve({"x-tenant-id": "globex"}) == "globex"
    assert r.resolve({"X-TENANT-ID": "globex"}) == "globex"
    assert r.resolve({"x-other": "no"}) == "default"


def test_bearer_resolver_maps_token_to_tenant() -> None:
    r = BearerTokenTenantResolver({"a-token": "acme", "b-token": "globex"})
    assert r.resolve({"authorization": "Bearer a-token"}) == "acme"
    assert r.resolve({"authorization": "Bearer b-token"}) == "globex"


def test_bearer_resolver_rejects_unknown_token() -> None:
    r = BearerTokenTenantResolver({"a-token": "acme"})
    with pytest.raises(PermissionError):
        r.resolve({"authorization": "Bearer ghost"})


def test_bearer_resolver_rejects_invalid_scheme() -> None:
    r = BearerTokenTenantResolver({"a-token": "acme"})
    with pytest.raises(PermissionError):
        r.resolve({"authorization": "Basic something"})


def test_bearer_resolver_optional_token_falls_back_to_default() -> None:
    r = BearerTokenTenantResolver({"a-token": "acme"})  # default require=False
    assert r.resolve({}) == "default"


def test_bearer_resolver_required_token_blocks_anonymous() -> None:
    r = BearerTokenTenantResolver({"a": "acme"}, require_token=True)
    with pytest.raises(PermissionError):
        r.resolve({})


def test_make_tenant_resolver_picks_strategy() -> None:
    assert isinstance(make_tenant_resolver(static="acme"), StaticTenantResolver)
    assert isinstance(make_tenant_resolver(tokens={"t": "x"}), BearerTokenTenantResolver)
    assert isinstance(make_tenant_resolver(), HeaderTenantResolver)


def test_runtime_checkable_protocol() -> None:
    assert isinstance(StaticTenantResolver(), TenantResolver)
    assert isinstance(HeaderTenantResolver(), TenantResolver)
    assert isinstance(BearerTokenTenantResolver({}), TenantResolver)


# --------------------------------------------------------------------------- #
# Persistence — tenant filter                                                  #
# --------------------------------------------------------------------------- #


def test_session_request_default_tenant() -> None:
    req = SessionRequest(task="hi")
    assert req.tenant_id == "default"


def test_persistence_tenant_helpers_filter_correctly() -> None:
    """list_thread_ids_for_tenant only returns same‑tenant threads."""

    from agentnet.graph import run_session

    cp = MemorySaver()
    run_session(
        SessionRequest(task="acme idea", tenant_id="acme"), thread_id="t-acme", checkpointer=cp
    )
    run_session(
        SessionRequest(task="globex idea", tenant_id="globex"),
        thread_id="t-globex",
        checkpointer=cp,
    )
    assert get_thread_tenant("t-acme", cp) == "acme"
    assert get_thread_tenant("t-globex", cp) == "globex"
    assert get_thread_tenant("t-missing", cp) is None
    # MemorySaver doesn't expose a SQL conn, so list_thread_ids returns
    # []; we only assert the function is total and tenant-safe.
    assert list_thread_ids_for_tenant(cp, "acme") == []
    assert list_thread_ids(cp) == []


# --------------------------------------------------------------------------- #
# HTTP API — tenant isolation                                                  #
# --------------------------------------------------------------------------- #


def _wait_for_state(
    client: TestClient, session_id: str, tenant: str | None = None
) -> dict[str, Any]:
    headers = {"X-Tenant-Id": tenant} if tenant else None
    for _ in range(50):
        r = client.get(f"/api/session/{session_id}/state", headers=headers)
        if r.status_code == 200:
            return r.json()  # type: ignore[no-any-return]
    raise AssertionError(f"session {session_id} never reached terminal state")


@pytest.fixture()
def header_client() -> Iterator[TestClient]:
    """API with HeaderTenantResolver — multi-tenant test harness."""

    cp = MemorySaver()
    app = make_app(checkpointer=cp, tenant_resolver=HeaderTenantResolver())
    with TestClient(app) as client:
        yield client


def test_api_session_isolated_by_header_tenant(header_client: TestClient) -> None:
    # acme creates a session
    r = header_client.post(
        "/api/session/start",
        json={"task": "acme task", "thread_id": "t-acme-1"},
        headers={"X-Tenant-Id": "acme"},
    )
    assert r.status_code == 202
    state = _wait_for_state(header_client, "t-acme-1", tenant="acme")
    assert state["tenant_id"] == "acme"

    # globex cannot see acme's session
    r = header_client.get(
        "/api/session/t-acme-1/state",
        headers={"X-Tenant-Id": "globex"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "session_not_found"

    # globex can't approve into it either
    r = header_client.post(
        "/api/session/t-acme-1/approve",
        json={"step_id": 1, "decision": "approve"},
        headers={"X-Tenant-Id": "globex"},
    )
    assert r.status_code == 404


def test_api_sessions_list_filters_by_tenant(header_client: TestClient) -> None:
    """GET /api/sessions only returns the caller's threads."""

    header_client.post(
        "/api/session/start",
        json={"task": "a", "thread_id": "t-a"},
        headers={"X-Tenant-Id": "acme"},
    )
    header_client.post(
        "/api/session/start",
        json={"task": "g", "thread_id": "t-g"},
        headers={"X-Tenant-Id": "globex"},
    )
    _wait_for_state(header_client, "t-a", tenant="acme")
    _wait_for_state(header_client, "t-g", tenant="globex")

    r = header_client.get("/api/sessions", headers={"X-Tenant-Id": "acme"})
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == "acme"
    assert "t-a" in body["threads"]
    assert "t-g" not in body["threads"]


def test_api_session_start_body_tenant_must_match_auth(header_client: TestClient) -> None:
    """A body that disagrees with the authenticated tenant is forbidden."""

    r = header_client.post(
        "/api/session/start",
        json={"task": "x", "tenant_id": "globex"},
        headers={"X-Tenant-Id": "acme"},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "tenant_mismatch"


def test_api_static_resolver_default_tenant_smoke() -> None:
    """The default StaticTenantResolver keeps single‑tenant deployments working."""

    cp = MemorySaver()
    app = make_app(checkpointer=cp)
    with TestClient(app) as client:
        client.post(
            "/api/session/start",
            json={"task": "hello", "thread_id": "t-default"},
        )
        _wait_for_state(client, "t-default")
        r = client.get("/api/sessions")
        assert r.status_code == 200
        assert r.json() == {"tenant_id": "default", "threads": ["t-default"]}


def test_api_bearer_token_resolver_unauthorized_returns_401() -> None:
    cp = MemorySaver()
    resolver = BearerTokenTenantResolver({"good-token": "acme"})
    app = make_app(checkpointer=cp, tenant_resolver=resolver)
    with TestClient(app) as client:
        r = client.get("/api/sessions", headers={"Authorization": "Bearer ghost"})
        assert r.status_code == 401
        assert r.json()["error"]["code"] == "unauthorized"

        r = client.get("/api/sessions", headers={"Authorization": "Bearer good-token"})
        assert r.status_code == 200
        assert r.json()["tenant_id"] == "acme"
