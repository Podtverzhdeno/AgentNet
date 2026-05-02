"""Long-term memory module.

Phase 2.E adds a real vector-store interface alongside the legacy
substring-search :class:`InMemoryStore`. Exports:

* :class:`MemoryRecord`, :class:`MemoryHit` — vector-store types.
* :class:`Embedder`, :class:`HashEmbedder`, :class:`OpenAIEmbedder`,
  :class:`OllamaEmbedder` — embedders.
* :class:`VectorStore`, :class:`InMemoryVectorStore`,
  :class:`QdrantVectorStore` — store implementations.
* :func:`make_vector_store` — spec/env-driven factory.
* :class:`InMemoryStore`, :class:`MemoryItem` — legacy substring store.
"""

from __future__ import annotations

from .embeddings import Embedder, HashEmbedder, OllamaEmbedder, OpenAIEmbedder
from .factory import make_vector_store
from .legacy import InMemoryStore, MemoryItem
from .qdrant import QdrantVectorStore
from .store import InMemoryVectorStore, VectorStore
from .types import MemoryHit, MemoryRecord

__all__ = [
    "Embedder",
    "HashEmbedder",
    "InMemoryStore",
    "InMemoryVectorStore",
    "MemoryHit",
    "MemoryItem",
    "MemoryRecord",
    "OllamaEmbedder",
    "OpenAIEmbedder",
    "QdrantVectorStore",
    "VectorStore",
    "make_vector_store",
]
