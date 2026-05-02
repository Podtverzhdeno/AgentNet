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
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

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


def _async_uri_to_path(uri: str) -> str:
    """Translate a URI used by :func:`make_checkpointer` to a file path.

    Returns the literal ``":memory:"`` for in-memory URIs.
    """

    normalized = (uri or "memory").strip()
    if normalized in {"sqlite::memory:", "sqlite:///:memory:", ":memory:"}:
        return ":memory:"
    if normalized.startswith("sqlite:///"):
        return normalized.removeprefix("sqlite:///")
    if normalized.startswith("sqlite://"):
        return normalized.removeprefix("sqlite://")
    return normalized


@asynccontextmanager
async def async_checkpointer(uri: str | None) -> AsyncIterator[BaseCheckpointSaver[Any]]:
    """Yield an *async* checkpointer compatible with the same URIs as
    :func:`make_checkpointer`.

    Empty / ``"memory"`` → :class:`MemorySaver` (it implements both the
    sync and async checkpoint protocols).

    Anything else is treated as SQLite and wrapped in an
    :class:`AsyncSqliteSaver` over an :mod:`aiosqlite` connection. The
    connection is closed when the context manager exits.
    """

    normalized = (uri or "memory").strip()
    if normalized in {"", "memory"}:
        yield MemorySaver()
        return

    path = _async_uri_to_path(normalized)
    if path != ":memory:":
        # The work below touches the local filesystem synchronously, but
        # connection bring-up is one-shot at app startup so a brief
        # blocking call is fine and avoids pulling in trio/anyio.path.
        target = Path(path).expanduser()  # noqa: ASYNC240
        target.parent.mkdir(parents=True, exist_ok=True)  # noqa: ASYNC240
        path = str(target)
    async with aiosqlite.connect(path) as conn:
        saver = AsyncSqliteSaver(conn)
        await saver.setup()
        yield saver


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


def get_thread_tenant(thread_id: str, checkpointer: BaseCheckpointSaver[Any]) -> str | None:
    """Return the ``tenant_id`` recorded in the persisted state, or ``None``.

    Used by the API layer to enforce tenant isolation on individual
    ``GET /state`` / ``POST /approve`` requests. Returns ``None`` when
    there's no checkpoint for the thread (so the caller can return 404).
    """

    from langchain_core.runnables import RunnableConfig

    config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    tup = checkpointer.get_tuple(config)
    if tup is None:
        return None
    state = tup.checkpoint.get("channel_values", {})
    if isinstance(state, dict):
        tenant = state.get("tenant_id")
        if isinstance(tenant, str):
            return tenant
    return None


def list_thread_ids_for_tenant(checkpointer: BaseCheckpointSaver[Any], tenant: str) -> list[str]:
    """List thread ids that belong to *tenant*.

    Iterates :func:`list_thread_ids` and filters by the persisted
    ``tenant_id`` field. Threads that don't carry the field at all are
    treated as belonging to ``"default"`` for backward compatibility
    with sessions created before Phase 3.A.
    """

    out: list[str] = []
    for tid in list_thread_ids(checkpointer):
        recorded = get_thread_tenant(tid, checkpointer) or "default"
        if recorded == tenant:
            out.append(tid)
    return sorted(out)


__all__ = [
    "DEFAULT_CHECKPOINT_DIR",
    "DEFAULT_CHECKPOINT_FILE",
    "async_checkpointer",
    "default_checkpoint_uri",
    "get_thread_tenant",
    "list_thread_ids",
    "list_thread_ids_for_tenant",
    "make_checkpointer",
]
