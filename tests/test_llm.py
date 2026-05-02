"""Tests for the pluggable LLM client layer (Phase 2.A).

Covers:

* :class:`MockLLMClient` deterministic fallback.
* :func:`make_llm_client` factory routing and env-var resolution.
* Anthropic / OpenAI / Ollama HTTP adapters via ``pytest-httpx``.
* Graph integration: ``build_graph(llm=...)`` threads a real client into
  the worker agents and the resulting state reflects the LLM output.
"""

from __future__ import annotations

import json

import pytest
from langgraph.checkpoint.memory import MemorySaver

from agentnet.graph import build_graph, run_session
from agentnet.llm import (
    AnthropicLLMClient,
    ChatMessage,
    LLMClient,
    MockLLMClient,
    OllamaLLMClient,
    OpenAILLMClient,
    make_llm_client,
    parse_llm_spec,
)
from agentnet.state import GraphState, SessionRequest

# --------------------------------------------------------------------------- #
# Mock client + factory                                                       #
# --------------------------------------------------------------------------- #


def test_mock_client_default_responder_echoes_user() -> None:
    client = MockLLMClient()
    resp = client.complete([ChatMessage(role="user", content="hello world")])
    assert resp.content.startswith("mock:")
    assert "hello world" in resp.content
    assert resp.model == "mock"


def test_mock_client_custom_responder() -> None:
    client = MockLLMClient(responder=lambda msgs: f"got:{len(msgs)}")
    resp = client.complete(
        [
            ChatMessage(role="system", content="be terse"),
            ChatMessage(role="user", content="ping"),
        ]
    )
    assert resp.content == "got:2"


def test_parse_llm_spec_round_trip() -> None:
    assert parse_llm_spec(None) == ("mock", None)
    assert parse_llm_spec("") == ("mock", None)
    assert parse_llm_spec("mock") == ("mock", None)
    assert parse_llm_spec("openai") == ("openai", None)
    assert parse_llm_spec("openai:gpt-4o-mini") == ("openai", "gpt-4o-mini")
    assert parse_llm_spec("Anthropic:Claude-3-5-Haiku") == ("anthropic", "Claude-3-5-Haiku")


def test_factory_default_is_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTNET_LLM", raising=False)
    client = make_llm_client(None)
    assert isinstance(client, MockLLMClient)


def test_factory_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENTNET_LLM", "mock")
    assert isinstance(make_llm_client(None), MockLLMClient)
    monkeypatch.setenv("AGENTNET_LLM", "openai:gpt-4o-mini")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    client = make_llm_client(None)
    assert isinstance(client, OpenAILLMClient)
    assert client.model == "gpt-4o-mini"


def test_factory_anthropic_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        make_llm_client("anthropic")


def test_factory_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unsupported LLM provider"):
        make_llm_client("mistral:tiny")


def test_factory_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = make_llm_client("anthropic", model="claude-3-5-haiku-20241022", api_key="injected")
    assert isinstance(client, AnthropicLLMClient)
    assert client.model == "claude-3-5-haiku-20241022"
    assert client.api_key == "injected"


# --------------------------------------------------------------------------- #
# HTTP adapters via pytest-httpx                                              #
# --------------------------------------------------------------------------- #


def test_anthropic_client_round_trip(httpx_mock):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="POST",
        url="https://api.anthropic.com/v1/messages",
        json={
            "model": "claude-3-5-haiku-20241022",
            "content": [{"type": "text", "text": "hello from claude"}],
            "usage": {"input_tokens": 5, "output_tokens": 7},
        },
    )
    client = AnthropicLLMClient(api_key="sk-ant-test")
    resp = client.complete(
        [
            ChatMessage(role="system", content="be terse"),
            ChatMessage(role="user", content="hi"),
        ]
    )
    assert resp.content == "hello from claude"
    assert resp.usage["input_tokens"] == 5
    request = httpx_mock.get_request()
    assert request is not None
    body = json.loads(request.content)
    assert body["system"] == "be terse"
    assert body["messages"] == [{"role": "user", "content": "hi"}]
    assert request.headers["x-api-key"] == "sk-ant-test"
    assert request.headers["anthropic-version"]


def test_openai_client_round_trip(httpx_mock):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="POST",
        url="https://api.openai.com/v1/chat/completions",
        json={
            "model": "gpt-4o-mini",
            "choices": [{"message": {"role": "assistant", "content": "hello from gpt"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4},
        },
    )
    client = OpenAILLMClient(api_key="sk-openai-test")
    resp = client.complete([ChatMessage(role="user", content="hi")])
    assert resp.content == "hello from gpt"
    assert resp.usage["prompt_tokens"] == 3
    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers["authorization"] == "Bearer sk-openai-test"


def test_ollama_client_round_trip(httpx_mock):  # type: ignore[no-untyped-def]
    httpx_mock.add_response(
        method="POST",
        url="http://127.0.0.1:11434/api/chat",
        json={
            "model": "llama3",
            "message": {"role": "assistant", "content": "hi from local"},
            "prompt_eval_count": 2,
            "eval_count": 8,
        },
    )
    client = OllamaLLMClient()
    resp = client.complete([ChatMessage(role="user", content="ping")])
    assert resp.content == "hi from local"
    assert resp.usage == {"prompt_tokens": 2, "completion_tokens": 8}


# --------------------------------------------------------------------------- #
# Graph integration                                                           #
# --------------------------------------------------------------------------- #


class _CannedClient:
    """A minimal ``LLMClient`` that always returns *content*."""

    model = "canned"

    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[list[ChatMessage]] = []

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,  # noqa: ARG002
        temperature: float = 0.0,  # noqa: ARG002
    ):
        from agentnet.llm.client import LLMResponse

        self.calls.append(list(messages))
        return LLMResponse(content=self.content, model=self.model)


def test_build_graph_with_mock_keeps_legacy_output() -> None:
    """Passing a MockLLMClient must NOT change deterministic behaviour."""

    graph_default = build_graph()
    graph_mock = build_graph(llm=MockLLMClient())
    state: GraphState = {
        "idea": "compare",
        "iteration": 1,
        "max_iterations": 1,
        "score_threshold": 1.0,
        "mode": "auto",
        "session_id": "compare",
    }
    out_default = graph_default.invoke(dict(state))
    out_mock = graph_mock.invoke(dict(state))
    assert out_default["research"]["summary"] == out_mock["research"]["summary"]


def test_build_graph_with_real_client_passes_through_response() -> None:
    """Real client triggers JSON-aware research/architect/etc agents."""

    payload = {
        "questions": ["q1"],
        "findings": [{"claim": "c", "confidence": 0.9, "sources": []}],
        "summary": "from the LLM",
        "sources": ["https://example.com"],
    }
    client = _CannedClient(json.dumps(payload))
    graph = build_graph(llm=client)
    state: GraphState = {
        "idea": "build platform",
        "iteration": 1,
        "max_iterations": 1,
        "score_threshold": 1.0,
        "mode": "auto",
        "session_id": "llm-graph",
    }
    out = graph.invoke(dict(state))
    assert out["research"]["summary"] == "from the LLM"
    # all four agents should have been called
    assert len(client.calls) == 4


def test_run_session_with_llm_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGENTNET_LLM", raising=False)
    cp = MemorySaver()
    result = run_session(
        SessionRequest(task="design analytics", max_iterations=1),
        thread_id="t-llm-1",
        checkpointer=cp,
        llm_spec="mock",
    )
    assert result.session_id == "t-llm-1"


def test_llm_client_protocol_runtime_check() -> None:
    assert isinstance(MockLLMClient(), LLMClient)
    assert isinstance(_CannedClient("x"), LLMClient)
