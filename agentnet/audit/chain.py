"""Hash‑chain utilities for the audit log."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from .events import AuditEvent

GENESIS_HASH = "GENESIS"


def _canonical(event: AuditEvent) -> bytes:
    """Stable JSON for hashing: sort keys, drop ``hash`` itself."""

    payload = event.model_dump()
    payload.pop("hash", None)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def compute_event_hash(prev_hash: str, event: AuditEvent) -> str:
    """Return ``sha256(prev_hash || canonical(event_without_hash))``."""

    h = hashlib.sha256()
    h.update(prev_hash.encode("utf-8"))
    h.update(b"|")
    h.update(_canonical(event))
    return h.hexdigest()


def verify_chain(events: Iterable[AuditEvent]) -> bool:
    """True if every event's ``hash`` matches and links to its predecessor.

    The first event must reference :data:`GENESIS_HASH` as ``prev_hash``.
    Returns ``False`` (without raising) on any tampered event so callers
    can decide how loud to be.
    """

    prev = GENESIS_HASH
    seen = False
    for event in events:
        seen = True
        if event.prev_hash != prev:
            return False
        if compute_event_hash(prev, event) != event.hash:
            return False
        prev = event.hash
    return seen or True  # an empty chain is trivially valid
