"""Tests for the persistence layer (LangGraph checkpointer wiring)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from agentnet import SessionRequest, run_session
from agentnet.cli import app
from agentnet.graph import get_session_state
from agentnet.persistence import (
    default_checkpoint_uri,
    list_thread_ids,
    make_checkpointer,
)

runner = CliRunner()


def test_default_checkpoint_uri_is_sqlite() -> None:
    assert default_checkpoint_uri().startswith("sqlite:///")


def test_make_checkpointer_default_is_in_memory() -> None:
    cp = make_checkpointer()
    # in-memory MemorySaver doesn't expose a `.conn` attribute
    assert getattr(cp, "conn", None) is None


def test_make_checkpointer_sqlite_in_memory_has_conn() -> None:
    cp = make_checkpointer("sqlite::memory:")
    assert getattr(cp, "conn", None) is not None


def test_session_persists_and_can_be_retrieved() -> None:
    cp = make_checkpointer("sqlite::memory:")
    result = run_session(
        SessionRequest(task="design analytics platform"),
        thread_id="t-test-1",
        checkpointer=cp,
    )
    assert result.session_id == "t-test-1"
    assert "t-test-1" in list_thread_ids(cp)
    state = get_session_state("t-test-1", cp)
    assert state is not None
    assert state.get("score") == result.score
    assert "result" in state


def test_session_state_is_none_for_unknown_thread() -> None:
    cp = make_checkpointer("sqlite::memory:")
    assert get_session_state("missing", cp) is None


def test_make_checkpointer_writes_to_disk(tmp_path) -> None:
    db = tmp_path / "checkpoints.sqlite"
    uri = f"sqlite:///{db}"
    cp = make_checkpointer(uri)
    run_session(
        SessionRequest(task="x"),
        thread_id="t-disk-1",
        checkpointer=cp,
    )
    assert db.exists() and db.stat().st_size > 0
    # reopen to make sure persistence survives a fresh checkpointer instance
    cp2 = make_checkpointer(uri)
    assert "t-disk-1" in list_thread_ids(cp2)


def test_cli_session_list_and_get_round_trip(tmp_path) -> None:
    db = tmp_path / "cli.sqlite"
    uri = f"sqlite:///{db}"

    start = runner.invoke(
        app,
        [
            "session",
            "start",
            "design analytics",
            "--persist",
            uri,
            "--thread-id",
            "t-cli-1",
            "--json",
        ],
    )
    assert start.exit_code == 0, start.output
    payload = json.loads(start.stdout)
    assert payload["session_id"] == "t-cli-1"

    listed = runner.invoke(app, ["session", "list", "--persist", uri, "--json"])
    assert listed.exit_code == 0
    assert "t-cli-1" in json.loads(listed.stdout)["threads"]

    fetched = runner.invoke(app, ["session", "get", "t-cli-1", "--persist", uri])
    assert fetched.exit_code == 0
    assert "t-cli-1" in fetched.stdout
