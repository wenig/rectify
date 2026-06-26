"""In-memory login throttle, keyed by client IP.

A single owner password protects the whole deployment, so an unthrottled ``/login``
is an open brute-force target. This keeps a sliding window of recent *failed*
attempts per IP and locks the IP out once it crosses the threshold. State is
process-local (no external store) — fine for the single-instance self-host model;
a restart clears it.
"""

from __future__ import annotations

import time


class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 900) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: dict[str, list[float]] = {}

    def _prune(self, key: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        kept = [t for t in self._failures.get(key, []) if t > cutoff]
        if kept:
            self._failures[key] = kept
        else:
            self._failures.pop(key, None)
        return kept

    def is_blocked(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return len(self._prune(key, now)) >= self.max_attempts

    def record_failure(self, key: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._prune(key, now)
        self._failures.setdefault(key, []).append(now)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
