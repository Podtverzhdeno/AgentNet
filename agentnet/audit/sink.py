"""Audit sinks: in‑memory and append‑only file."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol, runtime_checkable

from .events import AuditEvent


@runtime_checkable
class AuditSink(Protocol):
    """Append + iterate. No update / delete by design (WORM)."""

    def append(self, event: AuditEvent) -> None: ...

    def __iter__(self) -> Iterator[AuditEvent]: ...

    def __len__(self) -> int: ...

    def latest_hash(self) -> str | None:
        """Return the ``hash`` of the most recent event, or ``None`` for empty sinks."""
        ...


class InMemoryAuditSink:
    """Thread‑safe list‑backed sink. Used by tests and ad‑hoc deployments."""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = threading.Lock()

    def append(self, event: AuditEvent) -> None:
        with self._lock:
            self._events.append(event)

    def __iter__(self) -> Iterator[AuditEvent]:
        with self._lock:
            return iter(list(self._events))

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)

    def latest_hash(self) -> str | None:
        with self._lock:
            return self._events[-1].hash if self._events else None


class FileAuditSink:
    """JSON‑lines audit sink with O_APPEND write semantics.

    Rewriting earlier lines is not supported by this class — that's the
    "WORM" property. Existing lines are read once on construction so a
    new recorder can continue the chain across restarts.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).expanduser()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        # Touch the file so subsequent reads / appends always succeed.
        if not self._path.exists():
            self._path.touch()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, event: AuditEvent) -> None:
        line = json.dumps(event.model_dump(), sort_keys=True, ensure_ascii=False, default=str)
        with self._lock, self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
            fh.flush()

    def __iter__(self) -> Iterator[AuditEvent]:
        with self._lock, self._path.open("r", encoding="utf-8") as fh:
            data = fh.readlines()
        for raw in data:
            raw = raw.strip()
            if not raw:
                continue
            yield AuditEvent.model_validate_json(raw)

    def __len__(self) -> int:
        return sum(1 for _ in self)

    def latest_hash(self) -> str | None:
        last: AuditEvent | None = None
        for ev in self:
            last = ev
        return last.hash if last else None


__all__ = ["AuditSink", "FileAuditSink", "InMemoryAuditSink"]
