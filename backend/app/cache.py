from __future__ import annotations

from threading import Lock

from cachetools import TTLCache

from app.schemas import ProfileResponse


class ProfileCache:
    def __init__(self, ttl_seconds: int, maxsize: int = 256):
        self._ttl = max(ttl_seconds, 0)
        self._lock = Lock()
        self._store: TTLCache[str, ProfileResponse] | None
        if self._ttl > 0:
            self._store = TTLCache(maxsize=maxsize, ttl=self._ttl)
        else:
            self._store = None

    def get(self, public_id: str) -> ProfileResponse | None:
        if self._store is None:
            return None
        with self._lock:
            return self._store.get(public_id.lower())

    def set(self, public_id: str, profile: ProfileResponse) -> None:
        if self._store is None:
            return
        with self._lock:
            self._store[public_id.lower()] = profile
