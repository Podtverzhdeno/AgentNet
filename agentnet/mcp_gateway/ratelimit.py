"""Simple sliding-window rate limiter (per key, per minute)."""

from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowRateLimiter:
    """Allow at most ``rpm`` requests per ``window_seconds`` per key.

    Implementation: per-key deque of timestamps; on each :meth:`acquire`
    we drop entries older than ``window_seconds`` and check the size.
    Memory is O(rpm * keys) — fine for a Phase 2 dev gateway, swap for
    Redis token-bucket in Phase 3.
    """

    def __init__(self, *, rpm: int, window_seconds: float = 60.0) -> None:
        if rpm <= 0:
            raise ValueError("rpm must be > 0")
        self._rpm = rpm
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str, *, now: float | None = None) -> bool:
        ts = now if now is not None else time.monotonic()
        with self._lock:
            bucket = self._hits.setdefault(key, deque())
            cutoff = ts - self._window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self._rpm:
                return False
            bucket.append(ts)
            return True

    def remaining(self, key: str, *, now: float | None = None) -> int:
        ts = now if now is not None else time.monotonic()
        with self._lock:
            bucket = self._hits.get(key)
            if not bucket:
                return self._rpm
            cutoff = ts - self._window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            return max(0, self._rpm - len(bucket))


__all__ = ["SlidingWindowRateLimiter"]
