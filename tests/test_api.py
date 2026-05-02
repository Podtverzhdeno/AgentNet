"""Tests for the FastAPI HTTP/SSE surface (Phase 2.D)."""

from __future__ import annotations

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from agentnet.api import SessionEventBus, make_app


@pytest.fixture()
def client() -> TestClient:
    cp = MemorySaver()
    with TestClient(make_app(checkpointer=cp)) as c:
        yield c


def _wait_for_state(client: TestClient, session_id: str, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = client.get(f"/api/session/{session_id}/state")
        if r.status_code == 200:
            data = r.json()
            if data.get("score") is not None:
                return data
        time.sleep(0.05)
    raise AssertionError(f"session {session_id} did not reach a final state in {timeout}s")


def test_healthz(client: TestClient) -> None:
    r = client.get("/api/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_unknown_session_state_is_404(client: TestClient) -> None:
    r = client.get("/api/session/unknown/state")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "session_not_found"


def test_start_returns_202_with_session_id(client: TestClient) -> None:
    r = client.post("/api/session/start", json={"task": "build platform", "thread_id": "t-api-1"})
    assert r.status_code == 202
    body = r.json()
    assert body["session_id"] == "t-api-1"
    assert body["status"] == "started"
    state = _wait_for_state(client, "t-api-1")
    assert state["score"] >= 0.0


def test_start_validates_input(client: TestClient) -> None:
    r = client.post("/api/session/start", json={"task": "x", "mode": "wat"})
    assert r.status_code == 422


def test_sessions_list_round_trip(client: TestClient) -> None:
    client.post("/api/session/start", json={"task": "y", "thread_id": "t-list-1"})
    _wait_for_state(client, "t-list-1")
    r = client.get("/api/sessions")
    assert r.status_code == 200
    assert "t-list-1" in r.json()["threads"]


def test_approve_records_decision(client: TestClient) -> None:
    r = client.post(
        "/api/session/whatever/approve",
        json={"step_id": 1, "decision": "approve", "comment": "ok"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "whatever"
    assert body["decision"] == "approve"
    assert body["status"] == "recorded"


def test_stream_yields_session_events(client: TestClient) -> None:
    # start the session first; the bus buffers events and the subscriber
    # below replays them on connect, so we don't have to race the producer.
    r = client.post("/api/session/start", json={"task": "z", "thread_id": "t-stream-1"})
    assert r.status_code == 202
    _wait_for_state(client, "t-stream-1")

    with client.stream(
        "GET",
        "/api/session/t-stream-1/stream",
        headers={"Accept": "text/event-stream"},
    ) as stream_resp:
        events: list[dict] = []
        deadline = time.monotonic() + 10.0
        for raw in stream_resp.iter_lines():
            if time.monotonic() > deadline:
                break
            if not raw or not raw.startswith("data:"):
                continue
            payload = raw.removeprefix("data:").strip()
            if not payload:
                continue
            try:
                ev = json.loads(payload)
            except json.JSONDecodeError:
                continue
            events.append(ev)
            if ev.get("event") == "session.end":
                break

    kinds = [e.get("event") for e in events]
    assert "session.start" in kinds
    assert any(k == "node.update" for k in kinds)
    assert "session.end" in kinds


@pytest.mark.asyncio
async def test_event_bus_replays_to_late_subscribers() -> None:
    bus = SessionEventBus()
    await bus.publish("s1", {"event": "session.start"})
    await bus.publish("s1", {"event": "node.update", "node": "planner"})

    received: list[dict] = []

    async def consume() -> None:
        async for ev in bus.subscribe("s1"):
            received.append(ev)
            if ev.get("event") == "session.end":
                return

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await bus.publish("s1", {"event": "session.end"})
    await bus.mark_done("s1")
    await asyncio.wait_for(task, timeout=2.0)

    kinds = [e.get("event") for e in received]
    assert kinds[0] == "session.start"
    assert "session.end" in kinds
