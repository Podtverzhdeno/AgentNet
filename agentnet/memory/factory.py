"""Factory helpers for constructing vector stores from a string spec.

Spec syntax::

    None / "" / "memory"          → InMemoryVectorStore
    "qdrant"                       → QdrantVectorStore (env: QDRANT_URL,
                                     QDRANT_API_KEY, QDRANT_COLLECTION)
    "qdrant:<collection_name>"     → QdrantVectorStore with explicit collection
                                     (URL still from env/kwargs)

Lookup order when ``spec`` is ``None``:

1. ``AGENTNET_MEMORY`` env var.
2. Fall back to ``memory``.
"""

from __future__ import annotations

import os

from .embeddings import Embedder, HashEmbedder
from .qdrant import QdrantVectorStore
from .store import InMemoryVectorStore, VectorStore


def make_vector_store(
    spec: str | None = None,
    *,
    embedder: Embedder | None = None,
    collection: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> VectorStore:
    """Build a :class:`VectorStore` from *spec* / env, with overrides."""

    if spec is None or not spec.strip():
        spec = os.environ.get("AGENTNET_MEMORY")
    if spec is None or not spec.strip():
        return InMemoryVectorStore(embedder=embedder or HashEmbedder())

    head, _, tail = spec.strip().partition(":")
    provider = head.lower()
    spec_collection = tail.strip() or None

    if provider in ("memory", "in_memory", "mock"):
        return InMemoryVectorStore(embedder=embedder or HashEmbedder())

    if provider == "qdrant":
        # Qdrant URL/collection resolution:
        # 1. Explicit kwargs win (collection, base_url, api_key).
        # 2. Then fall back to spec parts.
        # 3. Then env vars.
        resolved_url = base_url or os.environ.get("QDRANT_URL")
        resolved_collection = collection or spec_collection or os.environ.get("QDRANT_COLLECTION")
        resolved_key = api_key or os.environ.get("QDRANT_API_KEY")
        if not resolved_url:
            raise RuntimeError("Qdrant requires a base URL (set QDRANT_URL or pass base_url=)")
        if not resolved_collection:
            raise RuntimeError(
                "Qdrant requires a collection name (set QDRANT_COLLECTION, "
                "spec qdrant:<name>, or pass collection=)"
            )
        return QdrantVectorStore(
            base_url=resolved_url,
            collection=resolved_collection,
            embedder=embedder or HashEmbedder(),
            api_key=resolved_key,
        )

    raise ValueError(f"unsupported memory provider {provider!r}")


__all__ = ["make_vector_store"]
