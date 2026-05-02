"""Canonical audit event types."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


def _now() -> float:
    return time.time()


def _gen_id() -> str:
    return f"evt-{uuid.uuid4().hex[:12]}"


class NewEvent(BaseModel):
    """Caller‑facing payload for :meth:`AuditRecorder.record`.

    The recorder fills in ``id`` / ``timestamp`` / ``prev_hash`` / ``hash``
    so business code never has to think about chain mechanics.
    """

    actor: str = Field(..., description="Who initiated the action (user / service id).")
    action: str = Field(..., description="Verb describing the action, e.g. 'session.start'.")
    resource: str = Field(..., description="Identifier of the resource the action targets.")
    tenant_id: str = "default"
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditEvent(BaseModel):
    """Persisted audit record with chain metadata.

    ``hash`` is sha256 of the canonical JSON of the event with that field
    blanked out, prefixed by ``prev_hash``. Equality on the dict
    representation is therefore stable — two recorders given the same
    input plus the same ``prev_hash`` produce identical events.
    """

    id: str = Field(default_factory=_gen_id)
    timestamp: float = Field(default_factory=_now)
    tenant_id: str = "default"
    actor: str
    action: str
    resource: str
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    hash: str
