"""Checkpoint persistence for the orchestrator graph.

LangGraph stores per-step state in a *checkpointer*. The platform supports
three flavours:

* ``memory`` (default) — in-process :class:`MemorySaver`. Lost on restart.
  Used by unit tests and ad-hoc CLI invocations.
* ``sqlite::memory:`` — :class:`SqliteSaver` over an in-memory SQLite
  connection. Same lifetime as the process but exercises the SQLite
  serialiser (useful in tests).
* ``sqlite:///path/to/file.db`` — :class:`SqliteSaver` on disk. Survives
  process restarts and is the recommended default for the local CLI.

For Phase 2 we deliberately stop at SQLite. Postgres / Redis support are
described in ``docs/INFRASTRUCTURE.md`` and will arrive in Phase 3 along
with multi-tenant deployment.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

DEFAULT_CHECKPOINT_DIR = Path.home() / ".agentnet"
DEFAULT_CHECKPOINT_FILE = "checkpoints.sqlite"


def default_checkpoint_uri() -> str:
    """URI of the disk-backed checkpointer used by the CLI by default."""

    return f"sqlite:///{DEFAULT_CHECKPOINT_DIR / DEFAULT_CHECKPOINT_FILE}"


def make_checkpointer(uri: str | None = None) -> BaseCheckpointSaver[Any]:
    """Build a checkpointer from a URI.

    Empty / ``None`` / ``"memory"`` → :class:`MemorySaver`.
    ``"sqlite::memory:"`` → SQLite in :memory:.
    ``"sqlite:///<path>"`` or a plain filesystem path → SQLite on disk.
    """

    normalized = (uri or "memory").strip()
    if normalized in {"", "memory"}:
        return MemorySaver()
    if normalized in {"sqlite::memory:", "sqlite:///:memory:"}:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        sqlite_saver: BaseCheckpointSaver[Any] = SqliteSaver(conn)
        SqliteSaver.setup(sqlite_saver)  # type: ignore[arg-type]
        return sqlite_saver

    if normalized.startswith("sqlite:///"):
        path = Path(normalized.removeprefix("sqlite:///"))
    elif normalized.startswith("sqlite://"):
        path = Path(normalized.removeprefix("sqlite://"))
    else:
        path = Path(normalized)
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path), check_same_thread=False)
    disk_saver: BaseCheckpointSaver[Any] = SqliteSaver(conn)
    SqliteSaver.setup(disk_saver)  # type: ignore[arg-type]
    return disk_saver


def list_thread_ids(checkpointer: BaseCheckpointSaver[Any]) -> list[str]:
    """Return distinct ``thread_id`` values stored by a SQLite checkpointer.

    LangGraph's checkpointer interface doesn't expose a "list all threads"
    method (it's per-thread by design), so for SQLite we query the table
    directly. Returns an empty list for non-SQLite checkpointers.
    """

    conn = getattr(checkpointer, "conn", None)
    if conn is None:
        return []
    rows = conn.execute("SELECT DISTINCT thread_id FROM checkpoints").fetchall()
    return [row[0] for row in rows]


__all__ = [
    "DEFAULT_CHECKPOINT_DIR",
    "DEFAULT_CHECKPOINT_FILE",
    "default_checkpoint_uri",
    "list_thread_ids",
    "make_checkpointer",
]
