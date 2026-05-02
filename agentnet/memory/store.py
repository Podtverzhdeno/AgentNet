"""Vector store interface and a process-local implementation.

The platform talks to long-term memory through :class:`VectorStore`.
Phase 2.E ships an in-process implementation (no deps, perfect for
tests) and an HTTP adapter for Qdrant — see :mod:`.qdrant`.
"""

from __future__ import annotations

import math
import threading
from typing import Protocol, runtime_checkable

from .embeddings import Embedder, HashEmbedder
from .types import MemoryHit, MemoryRecord


@runtime_checkable
class VectorStore(Protocol):
    """Contract every store implementation honours.

    Implementations enforce tenant isolation: ``search`` and ``delete``
    must never operate on records belonging to a different tenant.
    """

    def upsert(self, records: list[MemoryRecord]) -> list[MemoryRecord]: ...

    def search(
        self,
        query: str,
        *,
        tenant: str = "default",
        top_k: int = 5,
    ) -> list[MemoryHit]: ...

    def delete(self, ids: list[str], *, tenant: str = "default") -> int: ...


class InMemoryVectorStore:
    """Process-local cosine-similarity store.

    Suitable for tests, dev, and small deployments. Vectors are
    re-computed on insert from ``record.text`` using *embedder* — pass a
    :class:`HashEmbedder` (default) for fully deterministic behaviour.
    """

    def __init__(self, *, embedder: Embedder | None = None) -> None:
        self._embedder = embedder or HashEmbedder()
        self._records: dict[str, MemoryRecord] = {}
        self._vectors: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    @property
    def embedder(self) -> Embedder:
        return self._embedder

    @property
    def dimensions(self) -> int:
        return self._embedder.dimensions

    def upsert(self, records: list[MemoryRecord]) -> list[MemoryRecord]:
        if not records:
            return []
        vectors = self._embedder.embed_many([r.text for r in records])
        with self._lock:
            for record, vec in zip(records, vectors, strict=True):
                self._records[record.id] = record
                self._vectors[record.id] = vec
        return list(records)

    def search(
        self,
        query: str,
        *,
        tenant: str = "default",
        top_k: int = 5,
    ) -> list[MemoryHit]:
        if not query or top_k <= 0:
            return []
        qvec = self._embedder.embed(query)
        if _norm(qvec) == 0:
            return []
        with self._lock:
            candidates = [
                (rid, self._records[rid], self._vectors[rid])
                for rid, record in self._records.items()
                if record.tenant == tenant
            ]
        scored: list[MemoryHit] = []
        for _rid, record, vec in candidates:
            score = _cosine(qvec, vec)
            if score > 0:
                scored.append(MemoryHit(record=record, score=score))
        scored.sort(key=lambda h: h.score, reverse=True)
        return scored[:top_k]

    def delete(self, ids: list[str], *, tenant: str = "default") -> int:
        removed = 0
        with self._lock:
            for rid in ids:
                rec = self._records.get(rid)
                if rec is None or rec.tenant != tenant:
                    continue
                self._records.pop(rid, None)
                self._vectors.pop(rid, None)
                removed += 1
        return removed

    def __len__(self) -> int:
        with self._lock:
            return len(self._records)


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
    na = _norm(a)
    nb = _norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(v * v for v in values))


__all__ = ["InMemoryVectorStore", "VectorStore"]
