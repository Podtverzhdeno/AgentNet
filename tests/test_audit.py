"""Tests for Phase 3.C — append-only WORM audit log with hash chain."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from agentnet.api import make_app
from agentnet.audit import (
    GENESIS_HASH,
    AuditEvent,
    AuditRecorder,
    FileAuditSink,
    InMemoryAuditSink,
    NewEvent,
    compute_event_hash,
    verify_chain,
)


def _new(action: str, resource: str = "session-x", tenant: str = "default") -> NewEvent:
    return NewEvent(actor=tenant, action=action, resource=resource, tenant_id=tenant)


# --------------------------------------------------------------------------- #
# In-memory recorder & chain                                                   #
# --------------------------------------------------------------------------- #


def test_in_memory_recorder_links_chain_from_genesis() -> None:
    recorder = AuditRecorder(InMemoryAuditSink())
    e1 = recorder.record(_new("session.start"))
    e2 = recorder.record(_new("session.approve"))
    e3 = recorder.record(_new("session.end"))

    assert e1.prev_hash == GENESIS_HASH
    assert e2.prev_hash == e1.hash
    assert e3.prev_hash == e2.hash
    assert recorder.head == e3.hash
    assert recorder.verify() is True


def test_recorder_handles_concurrent_appends() -> None:
    """The recorder lock must serialise concurrent record() calls."""

    import threading

    recorder = AuditRecorder(InMemoryAuditSink())

    def worker() -> None:
        for _ in range(20):
            recorder.record(_new("tool.call"))

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    events = list(recorder.sink)
    assert len(events) == 100
    assert recorder.verify() is True


def test_verify_chain_detects_payload_tampering() -> None:
    sink = InMemoryAuditSink()
    recorder = AuditRecorder(sink)
    recorder.record(_new("session.start"))
    recorder.record(_new("session.approve"))

    # Mutate an event in-place — the recomputed hash now mismatches.
    events = list(sink)
    events[0].payload["injected"] = "evil"
    assert verify_chain(events) is False


def test_verify_chain_detects_link_tampering() -> None:
    sink = InMemoryAuditSink()
    recorder = AuditRecorder(sink)
    recorder.record(_new("a"))
    e2 = recorder.record(_new("b"))
    e2.prev_hash = "0" * 64  # break the link
    assert verify_chain(list(sink)) is False


def test_compute_event_hash_is_deterministic() -> None:
    e = AuditEvent(
        id="evt-fixed",
        timestamp=1_700_000_000.0,
        tenant_id="acme",
        actor="acme",
        action="session.start",
        resource="t-1",
        payload={"foo": "bar"},
        prev_hash=GENESIS_HASH,
        hash="",
    )
    h1 = compute_event_hash(GENESIS_HASH, e)
    h2 = compute_event_hash(GENESIS_HASH, e)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_verify_empty_chain_is_valid() -> None:
    assert verify_chain(iter([])) is True


# --------------------------------------------------------------------------- #
# File sink                                                                    #
# --------------------------------------------------------------------------- #


def test_file_sink_round_trip(tmp_path: Path) -> None:
    sink = FileAuditSink(tmp_path / "audit.jsonl")
    recorder = AuditRecorder(sink)
    recorder.record(_new("session.start", tenant="acme"))
    recorder.record(_new("session.end", tenant="acme"))

    # File contents are JSON Lines, one event per line.
    raw = sink.path.read_text(encoding="utf-8").splitlines()
    assert len(raw) == 2
    parsed = [json.loads(line) for line in raw]
    assert parsed[0]["action"] == "session.start"
    assert parsed[0]["prev_hash"] == GENESIS_HASH
    assert parsed[1]["prev_hash"] == parsed[0]["hash"]
    assert verify_chain(iter(sink)) is True


def test_file_sink_resumes_chain_across_restart(tmp_path: Path) -> None:
    """A new recorder reads the existing tail to continue hashing correctly."""

    path = tmp_path / "audit.jsonl"

    rec1 = AuditRecorder(FileAuditSink(path))
    rec1.record(_new("session.start"))
    e1_hash = rec1.head

    rec2 = AuditRecorder(FileAuditSink(path))
    e2 = rec2.record(_new("session.end"))
    assert e2.prev_hash == e1_hash

    # End-to-end chain still verifies after the restart.
    rec3 = AuditRecorder(FileAuditSink(path))
    assert rec3.verify() is True


def test_file_sink_o_append_doesnt_overwrite(tmp_path: Path) -> None:
    """append() must extend the file, never truncate."""

    path = tmp_path / "audit.jsonl"
    AuditRecorder(FileAuditSink(path)).record(_new("session.start"))
    size_after_first = path.stat().st_size
    AuditRecorder(FileAuditSink(path)).record(_new("session.end"))
    assert path.stat().st_size > size_after_first


# --------------------------------------------------------------------------- #
# API integration                                                              #
# --------------------------------------------------------------------------- #


@pytest.fixture()
def audit_client() -> Iterator[tuple[TestClient, AuditRecorder]]:
    cp = MemorySaver()
    recorder = AuditRecorder(InMemoryAuditSink())
    app = make_app(checkpointer=cp, audit_recorder=recorder)
    with TestClient(app) as client:
        yield client, recorder


def _wait_for_state(client: TestClient, session_id: str) -> None:
    for _ in range(50):
        r = client.get(f"/api/session/{session_id}/state")
        if r.status_code == 200:
            return
    raise AssertionError(f"session {session_id} never reached terminal state")


def test_api_session_start_records_audit_event(
    audit_client: tuple[TestClient, AuditRecorder],
) -> None:
    client, recorder = audit_client
    r = client.post(
        "/api/session/start",
        json={"task": "something", "thread_id": "t-audit-1"},
    )
    assert r.status_code == 202
    _wait_for_state(client, "t-audit-1")

    events = list(recorder.sink)
    starts = [e for e in events if e.action == "session.start"]
    assert len(starts) == 1
    assert starts[0].resource == "t-audit-1"
    assert starts[0].tenant_id == "default"
    assert starts[0].payload["task"] == "something"
    assert recorder.verify() is True


def test_api_approve_records_audit_event(
    audit_client: tuple[TestClient, AuditRecorder],
) -> None:
    client, recorder = audit_client
    client.post(
        "/api/session/start",
        json={"task": "y", "thread_id": "t-audit-2"},
    )
    _wait_for_state(client, "t-audit-2")
    r = client.post(
        "/api/session/t-audit-2/approve",
        json={"step_id": 3, "decision": "approve", "comment": "lgtm"},
    )
    assert r.status_code == 200

    approvals = [e for e in recorder.sink if e.action == "session.approve"]
    assert len(approvals) == 1
    assert approvals[0].resource == "t-audit-2"
    assert approvals[0].payload == {
        "step_id": 3,
        "decision": "approve",
        "comment": "lgtm",
    }
    assert recorder.verify() is True


def test_api_without_recorder_is_noop() -> None:
    """Backward-compat: make_app() without a recorder must keep working."""

    cp = MemorySaver()
    app = make_app(checkpointer=cp)
    with TestClient(app) as client:
        r = client.post("/api/session/start", json={"task": "no audit"})
        assert r.status_code == 202
