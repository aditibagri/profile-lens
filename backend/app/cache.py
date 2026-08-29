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

    def get(self, public_id: str, scope: str = "") -> ProfileResponse | None:
        if self._store is None:
            return None
        with self._lock:
            return self._store.get(self._key(public_id, scope))

    def set(self, public_id: str, profile: ProfileResponse, scope: str = "") -> None:
        if self._store is None:
            return
        with self._lock:
            self._store[self._key(public_id, scope)] = profile

    @staticmethod
    def _key(public_id: str, scope: str) -> str:
        pid = public_id.lower()
        return f"{pid}:{scope}" if scope else pid
