"""Tests for the vector memory module (Phase 2.E)."""

from __future__ import annotations

import json

import pytest

from agentnet.memory import (
    Embedder,
    HashEmbedder,
    InMemoryVectorStore,
    MemoryHit,
    MemoryRecord,
    OllamaEmbedder,
    OpenAIEmbedder,
    QdrantVectorStore,
    VectorStore,
    make_vector_store,
)

# --------------------------------------------------------------------------- #
# Embedders                                                                   #
# --------------------------------------------------------------------------- #


def test_hash_embedder_is_deterministic_and_normalised() -> None:
    e = HashEmbedder(dimensions=32)
    a = e.embed("hello world")
    b = e.embed("hello world")
    assert a == b
    norm = sum(x * x for x in a) ** 0.5
    assert norm == pytest.approx(1.0, abs=1e-6)


def test_hash_embedder_dim_validation() -> None:
    with pytest.raises(ValueError):
        HashEmbedder(dimensions=0)


def test_hash_embedder_handles_empty_text() -> None:
    e = HashEmbedder(dimensions=8)
    vec = e.embed("")
    assert vec == [0.0] * 8


def test_openai_embedder_round_trip(httpx_mock):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="POST",
        url="https://api.openai.com/v1/embeddings",
        json={
            "data": [
                {"embedding": [0.1] * 1536},
                {"embedding": [0.2] * 1536},
            ]
        },
    )
    e = OpenAIEmbedder(api_key="sk-test")
    out = e.embed_many(["hi", "there"])
    assert len(out) == 2
    assert out[0][0] == pytest.approx(0.1)
    request = httpx_mock.get_request()
    body = json.loads(request.content)  # type: ignore[union-attr]
    assert body["input"] == ["hi", "there"]


def test_ollama_embedder_round_trip(httpx_mock):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="POST",
        url="http://127.0.0.1:11434/api/embeddings",
        json={"embedding": [0.5] * 768},
    )
    e = OllamaEmbedder()
    vec = e.embed("ping")
    assert vec[:3] == [0.5, 0.5, 0.5]


# --------------------------------------------------------------------------- #
# InMemoryVectorStore                                                         #
# --------------------------------------------------------------------------- #


def test_in_memory_store_upsert_and_search() -> None:
    store = InMemoryVectorStore()
    store.upsert(
        [
            MemoryRecord(text="vector databases enable similarity search"),
            MemoryRecord(text="bananas grow on trees"),
            MemoryRecord(text="LangGraph orchestrates LLM agents"),
        ]
    )
    hits = store.search("similarity vectors", top_k=2)
    assert len(hits) <= 2
    assert hits
    assert "vector" in hits[0].record.text


def test_in_memory_store_tenant_isolation() -> None:
    store = InMemoryVectorStore()
    store.upsert(
        [
            MemoryRecord(text="acme top-secret architecture", tenant="acme"),
            MemoryRecord(text="other corp public note", tenant="other"),
        ]
    )
    acme_hits = store.search("architecture", tenant="acme")
    other_hits = store.search("architecture", tenant="other")
    assert acme_hits and all(h.record.tenant == "acme" for h in acme_hits)
    assert all(h.record.tenant != "acme" for h in other_hits)


def test_in_memory_store_delete_respects_tenant() -> None:
    store = InMemoryVectorStore()
    rec = MemoryRecord(text="delete me", tenant="acme")
    store.upsert([rec])
    # wrong tenant: no-op
    assert store.delete([rec.id], tenant="other") == 0
    # right tenant: removed
    assert store.delete([rec.id], tenant="acme") == 1
    assert len(store) == 0


def test_in_memory_store_returns_no_hits_for_empty_query() -> None:
    store = InMemoryVectorStore()
    store.upsert([MemoryRecord(text="something")])
    assert store.search("") == []
    assert store.search("nothing matches", top_k=0) == []


def test_vector_store_protocol_runtime_check() -> None:
    assert isinstance(InMemoryVectorStore(), VectorStore)


def test_embedder_protocol_runtime_check() -> None:
    assert isinstance(HashEmbedder(), Embedder)


# --------------------------------------------------------------------------- #
# Factory                                                                     #
# --------------------------------------------------------------------------- #


def test_factory_default_is_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTNET_MEMORY", raising=False)
    store = make_vector_store(None)
    assert isinstance(store, InMemoryVectorStore)


def test_factory_env_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTNET_MEMORY", "memory")
    assert isinstance(make_vector_store(None), InMemoryVectorStore)


def test_factory_qdrant_requires_url() -> None:
    with pytest.raises(RuntimeError, match="QDRANT_URL"):
        make_vector_store("qdrant", collection="x")


def test_factory_qdrant_inline_url() -> None:
    store = make_vector_store(
        "qdrant",
        base_url="https://qdrant.example",
        collection="agentnet",
        api_key="qd-test",
    )
    assert isinstance(store, QdrantVectorStore)
    assert store.collection == "agentnet"


def test_factory_qdrant_spec_collection_uses_env_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QDRANT_URL", "https://qdrant.example")
    monkeypatch.setenv("QDRANT_API_KEY", "env-key")
    store = make_vector_store("qdrant:agentnet")
    assert isinstance(store, QdrantVectorStore)
    assert store.base_url == "https://qdrant.example"
    assert store.collection == "agentnet"


def test_factory_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unsupported memory provider"):
        make_vector_store("pinecone")


# --------------------------------------------------------------------------- #
# QdrantVectorStore (HTTP wire format)                                         #
# --------------------------------------------------------------------------- #


def test_qdrant_creates_collection_when_missing(httpx_mock):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="GET",
        url="https://q.example/collections/notes",
        status_code=404,
        json={"status": {"error": "not found"}},
    )
    httpx_mock.add_response(
        method="PUT",
        url="https://q.example/collections/notes",
        json={"result": True, "status": "ok"},
    )
    httpx_mock.add_response(
        method="PUT",
        url="https://q.example/collections/notes/points?wait=true",
        json={"result": {"status": "completed"}},
    )
    store = QdrantVectorStore(base_url="https://q.example", collection="notes", api_key="qd-x")
    store.upsert([MemoryRecord(id="rec-1", text="hello", tenant="acme")])
    requests = httpx_mock.get_requests()
    assert any(r.url.path.endswith("/collections/notes") and r.method == "PUT" for r in requests)
    upsert_req = next(r for r in requests if r.url.path.endswith("/collections/notes/points"))
    body = json.loads(upsert_req.content)
    assert body["points"][0]["payload"]["tenant"] == "acme"
    assert body["points"][0]["payload"]["text"] == "hello"
    assert upsert_req.headers["api-key"] == "qd-x"


def test_qdrant_search_filters_by_tenant(httpx_mock):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="GET",
        url="https://q.example/collections/notes",
        json={"status": "ok", "result": {}},
    )
    httpx_mock.add_response(
        method="POST",
        url="https://q.example/collections/notes/points/search",
        json={
            "result": [
                {
                    "id": "rec-1",
                    "score": 0.92,
                    "payload": {
                        "text": "remembered thing",
                        "tenant": "acme",
                        "created_at": 0.0,
                        "extra": "kept",
                    },
                }
            ]
        },
    )
    store = QdrantVectorStore(base_url="https://q.example", collection="notes")
    hits = store.search("remembered", tenant="acme", top_k=3)
    assert len(hits) == 1
    assert isinstance(hits[0], MemoryHit)
    assert hits[0].record.tenant == "acme"
    assert hits[0].record.payload == {"extra": "kept"}
    search_req = next(
        r
        for r in httpx_mock.get_requests()
        if r.url.path.endswith("/collections/notes/points/search")
    )
    body = json.loads(search_req.content)
    assert body["filter"]["must"] == [{"key": "tenant", "match": {"value": "acme"}}]
    assert body["limit"] == 3


def test_qdrant_delete(httpx_mock):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="GET",
        url="https://q.example/collections/notes",
        json={"status": "ok", "result": {}},
    )
    httpx_mock.add_response(
        method="POST",
        url="https://q.example/collections/notes/points/delete?wait=true",
        json={"result": {"status": "completed"}},
    )
    store = QdrantVectorStore(base_url="https://q.example", collection="notes")
    removed = store.delete(["rec-1", "rec-2"], tenant="acme")
    assert removed == 2
    delete_req = next(
        r
        for r in httpx_mock.get_requests()
        if r.url.path.endswith("/collections/notes/points/delete")
    )
    body = json.loads(delete_req.content)
    assert body["points"] == ["rec-1", "rec-2"]
    assert body["filter"]["must"] == [{"key": "tenant", "match": {"value": "acme"}}]
