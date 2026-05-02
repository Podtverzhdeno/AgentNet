"""High‑level recorder that auto‑fills the hash chain."""

from __future__ import annotations

import threading

from .chain import GENESIS_HASH, compute_event_hash, verify_chain
from .events import AuditEvent, NewEvent
from .sink import AuditSink


class AuditRecorder:
    """Wrap an :class:`AuditSink` and produce a tamper‑evident chain.

    Thread‑safe: appends are serialised so the ``prev_hash`` link can't
    race even when many request handlers record concurrently.
    """

    def __init__(self, sink: AuditSink) -> None:
        self._sink = sink
        self._lock = threading.Lock()
        # Recover the chain head from the existing sink so a restart
        # continues hashing from where the previous process left off.
        self._head: str = sink.latest_hash() or GENESIS_HASH

    @property
    def sink(self) -> AuditSink:
        return self._sink

    @property
    def head(self) -> str:
        return self._head

    def record(self, new: NewEvent) -> AuditEvent:
        """Persist *new* and return the resulting :class:`AuditEvent`."""

        with self._lock:
            event_no_hash = AuditEvent(
                tenant_id=new.tenant_id,
                actor=new.actor,
                action=new.action,
                resource=new.resource,
                payload=new.payload,
                prev_hash=self._head,
                hash="",  # filled below
            )
            event_no_hash.hash = compute_event_hash(self._head, event_no_hash)
            self._sink.append(event_no_hash)
            self._head = event_no_hash.hash
            return event_no_hash

    def verify(self) -> bool:
        """Recompute all hashes and confirm the chain has not been tampered with."""

        return verify_chain(iter(self._sink))


__all__ = ["AuditRecorder"]
