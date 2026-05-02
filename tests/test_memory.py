"""Tests for the in-memory mock store."""

from __future__ import annotations

from agentnet.memory import InMemoryStore


def test_store_and_retrieve() -> None:
    store = InMemoryStore()
    item = store.store({"text": "hello world"})
    found = store.search("hello")
    assert any(i.id == item.id for i in found)


def test_search_respects_tenant() -> None:
    store = InMemoryStore()
    store.store({"text": "secret"}, tenant="acme")
    store.store({"text": "secret"}, tenant="other")
    assert len(store.search("secret", tenant="acme")) == 1


def test_delete() -> None:
    store = InMemoryStore()
    item = store.store({"text": "x"})
    assert store.delete(item.id)
    assert not store.search("x")
