"""Append-only JSON-Lines audit log for the MCP gateway.

Each call (success, denial, or error) gets one line. The format is
deliberately simple and append-only so it can be rotated by ``logrotate``
or shipped straight into a SIEM as raw JSON.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolCall:
    """One row in the audit log."""

    tool: str
    role: str
    params: dict[str, Any]
    duration_ms: float
    success: bool
    result: Any = None
    error: str | None = None
    ts: float = field(default_factory=time.time)


class AuditLog:
    """Thread-safe append-only JSON-Lines sink.

    If *path* is None the log is in-memory only (handy for tests). Buffered
    writes are flushed after every record to make the audit log durable
    even if the process crashes.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._mem: list[ToolCall] = []
        self._lock = threading.Lock()
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, call: ToolCall) -> None:
        with self._lock:
            self._mem.append(call)
            if self._path is None:
                return
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(call), default=str, ensure_ascii=False))
                fh.write("\n")
                fh.flush()

    def __iter__(self) -> Iterator[ToolCall]:
        with self._lock:
            return iter(list(self._mem))

    @property
    def entries(self) -> list[ToolCall]:
        with self._lock:
            return list(self._mem)


__all__ = ["AuditLog", "ToolCall"]
