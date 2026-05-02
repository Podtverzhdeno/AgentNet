"""Pydantic types for the vector memory store (Phase 2.E)."""

from __future__ import annotations

import time
import uuid
from typing import Any

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    """A single piece of remembered context.

    ``text`` is the searchable content; ``payload`` holds arbitrary
    metadata returned alongside hits. ``tenant`` is enforced by every
    store implementation — searches never cross tenants.
    """

    id: str = Field(default_factory=lambda: f"mem-{uuid.uuid4().hex[:12]}")
    text: str
    payload: dict[str, Any] = Field(default_factory=dict)
    tenant: str = "default"
    created_at: float = Field(default_factory=time.time)


class MemoryHit(BaseModel):
    """A search result: a record plus its similarity score in [0, 1]."""

    record: MemoryRecord
    score: float


__all__ = ["MemoryHit", "MemoryRecord"]
