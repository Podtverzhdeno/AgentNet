"""Tests for the public state schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentnet.state import SessionRequest


def test_session_request_defaults() -> None:
    req = SessionRequest(task="Hello world")
    assert req.task == "Hello world"
    assert req.mode == "auto"
    assert req.max_iterations == 3
    assert pytest.approx(req.score_threshold) == 0.8


def test_session_request_validates_threshold_bounds() -> None:
    with pytest.raises(ValidationError):
        SessionRequest(task="x", score_threshold=1.5)
    with pytest.raises(ValidationError):
        SessionRequest(task="x", score_threshold=-0.1)


def test_session_request_validates_max_iterations() -> None:
    with pytest.raises(ValidationError):
        SessionRequest(task="x", max_iterations=0)
    with pytest.raises(ValidationError):
        SessionRequest(task="x", max_iterations=999)
