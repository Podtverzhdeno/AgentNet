"""Embedders used by the vector store.

We ship three implementations:

* :class:`HashEmbedder` — deterministic, no deps, perfect for tests/CI.
* :class:`OpenAIEmbedder` — POST ``/v1/embeddings`` (OpenAI-compatible).
* :class:`OllamaEmbedder` — POST ``/api/embeddings`` against a local
  Ollama daemon.

All adapters expose :attr:`dimensions` so :class:`InMemoryVectorStore`
and :class:`QdrantVectorStore` can size their indices correctly.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol, runtime_checkable

import httpx


@runtime_checkable
class Embedder(Protocol):
    dimensions: int

    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic embedder built around the bag-of-tokens hashing
    trick. Same input → same vector, no network. Used by default in
    :class:`InMemoryVectorStore` and in unit tests.
    """

    def __init__(self, *, dimensions: int = 64) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be > 0")
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for token in self._tokenize(text):
            digest = hashlib.blake2s(token.encode("utf-8"), digest_size=8).digest()
            idx = int.from_bytes(digest[:4], "little") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            # Stable zero vector — search() will treat it as no match.
            return vec
        return [v / norm for v in vec]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return [tok for tok in text.lower().split() if tok]


class _BaseHTTPEmbedder:
    def __init__(self, *, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client()
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


class OpenAIEmbedder(_BaseHTTPEmbedder):
    """OpenAI / OpenAI-compatible embedder.

    Defaults to ``text-embedding-3-small`` (1536 dims). Pass ``base_url``
    to redirect to Together/Fireworks/OpenRouter/local vLLM.
    """

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "text-embedding-3-small",
        dimensions: int = 1536,
        base_url: str = "https://api.openai.com",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(client=client)
        if dimensions <= 0:
            raise ValueError("dimensions must be > 0")
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.base_url = base_url.rstrip("/")

    def embed(self, text: str) -> list[float]:
        return self.embed_many([text])[0]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = self._client.post(
            f"{self.base_url}/v1/embeddings",
            json={"model": self.model, "input": texts},
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        body = resp.json()
        data = body.get("data") or []
        return [list(map(float, item.get("embedding") or [])) for item in data]


class OllamaEmbedder(_BaseHTTPEmbedder):
    """Local Ollama ``/api/embeddings`` adapter."""

    def __init__(
        self,
        *,
        model: str = "nomic-embed-text",
        dimensions: int = 768,
        base_url: str = "http://127.0.0.1:11434",
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(client=client)
        if dimensions <= 0:
            raise ValueError("dimensions must be > 0")
        self.model = model
        self.dimensions = dimensions
        self.base_url = base_url.rstrip("/")

    def embed(self, text: str) -> list[float]:
        resp = self._client.post(
            f"{self.base_url}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=60.0,
        )
        resp.raise_for_status()
        body = resp.json()
        return list(map(float, body.get("embedding") or []))

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


__all__ = ["Embedder", "HashEmbedder", "OllamaEmbedder", "OpenAIEmbedder"]
