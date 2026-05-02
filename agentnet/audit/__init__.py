"""Append‑only audit log with a tamper‑evident hash chain (Phase 3.C).

Two layers:

* :class:`AuditEvent` — Pydantic model carrying the canonical fields
  every audit entry has (id, timestamp, tenant, actor, action, resource,
  payload). The :attr:`AuditEvent.hash` field is filled by the recorder
  as ``sha256(prev_hash || canonical_json(event_without_hash))``. The
  first event in a chain uses ``prev_hash = "GENESIS"``.
* :class:`AuditSink` Protocol — minimal "append + iterate" surface. Two
  implementations:
  - :class:`InMemoryAuditSink` for tests / single‑process deployments.
  - :class:`FileAuditSink` for real WORM‑style storage: JSON Lines
    file opened with ``O_APPEND``, one event per line; rewrites are
    not supported by the API and pre‑existing lines are read on
    construction so the chain continues correctly across restarts.

The :func:`verify_chain` helper recomputes every hash and confirms each
event's ``prev_hash`` matches the predecessor — call it on incident
response or to detect tampering.
"""

from __future__ import annotations

from .chain import GENESIS_HASH, compute_event_hash, verify_chain
from .events import AuditEvent, NewEvent
from .recorder import AuditRecorder
from .sink import AuditSink, FileAuditSink, InMemoryAuditSink

__all__ = [
    "GENESIS_HASH",
    "AuditEvent",
    "AuditRecorder",
    "AuditSink",
    "FileAuditSink",
    "InMemoryAuditSink",
    "NewEvent",
    "compute_event_hash",
    "verify_chain",
]
