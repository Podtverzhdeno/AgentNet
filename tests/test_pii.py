"""Tests for the PII guard module (Phase 3.B)."""

from __future__ import annotations

import re

import pytest

from agentnet.llm import ChatMessage, LLMResponse, MockLLMClient
from agentnet.pii import (
    DEFAULT_PATTERNS,
    PIIPattern,
    PIIType,
    Redactor,
    ScrubbedLLMClient,
)

# --------------------------------------------------------------------------- #
# Redactor — basic patterns                                                    #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected_marker", "expected_type"),
    [
        ("Reach me at alice@example.com please", "[REDACTED:EMAIL]", PIIType.EMAIL),
        ("call (415) 555-1234 today", "[REDACTED:PHONE]", PIIType.PHONE),
        ("card 4111-1111-1111-1111 expires", "[REDACTED:CC]", PIIType.CREDIT_CARD),
        ("ssn 123-45-6789 in the form", "[REDACTED:SSN]", PIIType.SSN),
        (
            "token eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.signaturePart",
            "[REDACTED:JWT]",
            PIIType.JWT,
        ),
        (
            "key sk-ant-abcdefghijklmnopqrstuvwx",
            "[REDACTED:KEY]",
            PIIType.API_KEY,
        ),
        ("github ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaa", "[REDACTED:KEY]", PIIType.API_KEY),
    ],
)
def test_redactor_matches_known_pii(
    text: str, expected_marker: str, expected_type: PIIType
) -> None:
    redactor = Redactor()
    findings = redactor.find(text)
    assert findings, f"expected to find PII in {text!r}"
    assert any(f.pii_type is expected_type for f in findings)
    assert expected_marker in redactor.redact(text)


def test_redactor_leaves_non_pii_alone() -> None:
    text = "the order arrived in 5 days, no PII here"
    redactor = Redactor()
    assert redactor.redact(text) == text
    assert redactor.find(text) == []


def test_redactor_handles_empty_input() -> None:
    redactor = Redactor()
    assert redactor.redact("") == ""
    assert redactor.find("") == []


def test_redactor_redacts_multiple_findings_in_order() -> None:
    text = "email alice@x.com and bob@y.io"
    redactor = Redactor()
    redacted = redactor.redact(text)
    assert redacted == "email [REDACTED:EMAIL] and [REDACTED:EMAIL]"


def test_redactor_overlap_priority_jwt_over_api_key() -> None:
    # JWT pattern is declared before API_KEY, so a JWT‑shaped string
    # never gets tagged as a generic key.
    text = "auth eyJabcdef12345.payloadpart789.signature1234"
    redactor = Redactor()
    findings = redactor.find(text)
    assert len(findings) == 1
    assert findings[0].pii_type is PIIType.JWT


def test_redactor_extra_pattern_appended() -> None:
    extra = PIIPattern.make(PIIType.OTHER, r"\bsecret-\w+\b", "[REDACTED:CUSTOM]")
    redactor = Redactor(extra=[extra])
    assert "[REDACTED:CUSTOM]" in redactor.redact("the secret-handshake is...")


def test_redactor_custom_patterns_replace_defaults() -> None:
    only_email = [p for p in DEFAULT_PATTERNS if p.pii_type is PIIType.EMAIL]
    redactor = Redactor(patterns=only_email)
    text = "email a@b.com card 4111 1111 1111 1111"
    out = redactor.redact(text)
    # email got scrubbed, card did not (we excluded it):
    assert "[REDACTED:EMAIL]" in out
    assert "4111 1111 1111 1111" in out


def test_redactor_payload_walks_nested_structures() -> None:
    redactor = Redactor()
    payload = {
        "user": {"email": "alice@example.com", "id": 1},
        "logs": ["please call (415) 555-1234", "ok"],
        "amount": 42,
    }
    scrubbed = redactor.redact_payload(payload)
    assert scrubbed["user"]["email"] == "[REDACTED:EMAIL]"
    assert scrubbed["user"]["id"] == 1
    assert scrubbed["logs"][0] == "please call [REDACTED:PHONE]"
    assert scrubbed["logs"][1] == "ok"
    assert scrubbed["amount"] == 42


def test_pii_pattern_make_compiles_regex() -> None:
    p = PIIPattern.make(PIIType.OTHER, r"\d+", "[N]")
    assert isinstance(p.pattern, re.Pattern)
    assert p.pattern.findall("a 1 b 2") == ["1", "2"]


# --------------------------------------------------------------------------- #
# ScrubbedLLMClient                                                            #
# --------------------------------------------------------------------------- #


def test_scrubbed_client_redacts_prompt_only_by_default() -> None:
    seen: list[str] = []

    def responder(messages: list[ChatMessage]) -> str:
        seen.append(messages[-1].content)
        # echo a NEW PII bit to validate response isn't redacted by default:
        return "thanks alice@example.com"

    inner = MockLLMClient(responder=responder)
    client = ScrubbedLLMClient(inner)
    resp = client.complete([ChatMessage(role="user", content="contact alice@example.com please")])
    assert seen == ["contact [REDACTED:EMAIL] please"]
    # response is NOT scrubbed by default:
    assert resp.content == "thanks alice@example.com"


def test_scrubbed_client_can_redact_response_too() -> None:
    inner = MockLLMClient(responder=lambda _: "thanks alice@example.com")
    client = ScrubbedLLMClient(inner, scrub_response=True)
    resp = client.complete([ChatMessage(role="user", content="hi")])
    assert resp.content == "thanks [REDACTED:EMAIL]"


def test_scrubbed_client_propagates_model_and_usage() -> None:
    class _Inner:
        model = "fake-1.0"

        def complete(
            self,
            messages: list[ChatMessage],  # noqa: ARG002
            *,
            max_tokens: int = 1024,  # noqa: ARG002
            temperature: float = 0.0,  # noqa: ARG002
        ) -> LLMResponse:
            return LLMResponse(content="ok", model=self.model, usage={"input_tokens": 7})

    client = ScrubbedLLMClient(_Inner())
    assert client.model == "fake-1.0"
    resp = client.complete([ChatMessage(role="user", content="x")])
    assert resp.usage["input_tokens"] == 7


def test_scrubbed_client_disables_prompt_scrub_when_requested() -> None:
    seen: list[str] = []

    def responder(messages: list[ChatMessage]) -> str:
        seen.append(messages[-1].content)
        return "ok"

    inner = MockLLMClient(responder=responder)
    client = ScrubbedLLMClient(inner, scrub_prompt=False)
    client.complete([ChatMessage(role="user", content="email alice@example.com")])
    assert seen == ["email alice@example.com"]
