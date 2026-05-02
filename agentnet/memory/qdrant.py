"""Qdrant adapter for :class:`agentnet.memory.VectorStore`.

We talk to Qdrant's REST API directly so we don't pull in
``qdrant-client`` as a runtime dep. Tests stub the wire format with
``pytest-httpx``.

Endpoints used:

* ``GET    /collections/{name}``               — existence check
* ``PUT    /collections/{name}``               — create with vector size
* ``PUT    /collections/{name}/points``        — upsert records
* ``POST   /collections/{name}/points/search`` — kNN with payload filter
* ``POST   /collections/{name}/points/delete`` — bulk delete by id

Tenant isolation is enforced in ``search`` and ``delete`` via a
``payload.tenant`` filter; records always carry ``tenant`` in their
payload at upsert time.
"""

from __future__ import annotations

from typing import Any

import httpx

from .embeddings import Embedder, HashEmbedder
from .types import MemoryHit, MemoryRecord


class QdrantVectorStore:
    """Vector store backed by a remote Qdrant cluster (REST)."""

    def __init__(
        self,
        *,
        base_url: str,
        collection: str,
        embedder: Embedder | None = None,
        api_key: str | None = None,
        distance: str = "Cosine",
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.collection = collection
        self._embedder = embedder or HashEmbedder()
        self._api_key = api_key
        self._distance = distance
        self._client = client or httpx.Client()
        self._owns_client = client is None
        self._collection_ready = False

    @property
    def embedder(self) -> Embedder:
        return self._embedder

    @property
    def dimensions(self) -> int:
        return self._embedder.dimensions

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _headers(self) -> dict[str, str]:
        h = {"content-type": "application/json"}
        if self._api_key:
            h["api-key"] = self._api_key
        return h

    def ensure_collection(self) -> None:
        """Idempotently create the collection if it doesn't exist."""

        if self._collection_ready:
            return
        resp = self._client.get(
            f"{self.base_url}/collections/{self.collection}",
            headers=self._headers(),
            timeout=30.0,
        )
        if resp.status_code == 200:
            self._collection_ready = True
            return
        if resp.status_code != 404:
            resp.raise_for_status()
        create = self._client.put(
            f"{self.base_url}/collections/{self.collection}",
            headers=self._headers(),
            json={
                "vectors": {
                    "size": self._embedder.dimensions,
                    "distance": self._distance,
                }
            },
            timeout=30.0,
        )
        create.raise_for_status()
        self._collection_ready = True

    def upsert(self, records: list[MemoryRecord]) -> list[MemoryRecord]:
        if not records:
            return []
        self.ensure_collection()
        vectors = self._embedder.embed_many([r.text for r in records])
        points: list[dict[str, Any]] = []
        for r, vec in zip(records, vectors, strict=True):
            payload: dict[str, Any] = dict(r.payload)
            payload["text"] = r.text
            payload["tenant"] = r.tenant
            payload["created_at"] = r.created_at
            points.append({"id": r.id, "vector": vec, "payload": payload})
        resp = self._client.put(
            f"{self.base_url}/collections/{self.collection}/points",
            params={"wait": "true"},
            headers=self._headers(),
            json={"points": points},
            timeout=60.0,
        )
        resp.raise_for_status()
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
        self.ensure_collection()
        qvec = self._embedder.embed(query)
        body: dict[str, Any] = {
            "vector": qvec,
            "limit": top_k,
            "with_payload": True,
            "filter": {
                "must": [{"key": "tenant", "match": {"value": tenant}}],
            },
        }
        resp = self._client.post(
            f"{self.base_url}/collections/{self.collection}/points/search",
            headers=self._headers(),
            json=body,
            timeout=60.0,
        )
        resp.raise_for_status()
        result = resp.json().get("result") or []
        hits: list[MemoryHit] = []
        for item in result:
            payload: dict[str, Any] = dict(item.get("payload") or {})
            text = str(payload.pop("text", ""))
            ten = str(payload.pop("tenant", tenant))
            created_at = float(payload.pop("created_at", 0.0))
            record = MemoryRecord(
                id=str(item.get("id")),
                text=text,
                payload=payload,
                tenant=ten,
                created_at=created_at,
            )
            hits.append(MemoryHit(record=record, score=float(item.get("score") or 0.0)))
        return hits

    def delete(self, ids: list[str], *, tenant: str = "default") -> int:
        if not ids:
            return 0
        self.ensure_collection()
        body = {
            "points": list(ids),
            "filter": {
                "must": [{"key": "tenant", "match": {"value": tenant}}],
            },
        }
        resp = self._client.post(
            f"{self.base_url}/collections/{self.collection}/points/delete",
            params={"wait": "true"},
            headers=self._headers(),
            json=body,
            timeout=60.0,
        )
        resp.raise_for_status()
        # Qdrant doesn't return per-id success counts here; treat the
        # request as best-effort and return the requested set size.
        return len(ids)


__all__ = ["QdrantVectorStore"]
