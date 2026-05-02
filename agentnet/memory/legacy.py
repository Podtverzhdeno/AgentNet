"""Legacy substring-search memory store (Phase 1).

Kept for backward compatibility; new code should use the vector
:class:`InMemoryVectorStore` / :class:`QdrantVectorStore` from
:mod:`agentnet.memory`. This module will be removed in a future phase
once nothing imports :class:`InMemoryStore` directly.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MemoryItem:
    id: str
    payload: dict[str, Any]
    tenant: str
    created_at: float = field(default_factory=time.time)


class InMemoryStore:
    """Process-local mock implementation of the memory store."""

    def __init__(self) -> None:
        self._items: dict[str, MemoryItem] = {}

    def store(self, payload: dict[str, Any], tenant: str = "default") -> MemoryItem:
        item = MemoryItem(id=f"mem-{uuid.uuid4().hex[:12]}", payload=payload, tenant=tenant)
        self._items[item.id] = item
        return item

    def search(self, query: str, tenant: str = "default", top_k: int = 5) -> list[MemoryItem]:
        q = query.lower()
        scored: list[tuple[int, MemoryItem]] = []
        for item in self._items.values():
            if item.tenant != tenant:
                continue
            haystack = " ".join(_iter_strings(item.payload)).lower()
            score = haystack.count(q)
            if score:
                scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [item for _, item in scored[:top_k]]

    def delete(self, item_id: str) -> bool:
        return self._items.pop(item_id, None) is not None

    def __len__(self) -> int:
        return len(self._items)


def _iter_strings(value: Any) -> list[str]:
    """Recursively collect string leaves from a JSON-like structure."""

    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for v in value.values():
            out.extend(_iter_strings(v))
        return out
    if isinstance(value, list | tuple | set):
        out = []
        for v in value:
            out.extend(_iter_strings(v))
        return out
    return []


__all__ = ["InMemoryStore", "MemoryItem"]
