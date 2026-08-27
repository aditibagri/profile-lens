from __future__ import annotations

import time
from collections import deque
from threading import Lock


class RateLimiter:
    """Simple sliding-window limiter (process-local)."""

    def __init__(self, max_calls: int, period_seconds: float = 60.0):
        self.max_calls = max(max_calls, 1)
        self.period_seconds = period_seconds
        self._calls: deque[float] = deque()
        self._lock = Lock()

    def allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            while self._calls and now - self._calls[0] >= self.period_seconds:
                self._calls.popleft()
            if len(self._calls) >= self.max_calls:
                return False
            self._calls.append(now)
            return True

    def retry_after(self) -> int:
        with self._lock:
            if not self._calls:
                return 0
            oldest = self._calls[0]
        remaining = self.period_seconds - (time.monotonic() - oldest)
        return max(int(remaining) + 1, 1)
