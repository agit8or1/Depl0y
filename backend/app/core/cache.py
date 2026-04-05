import time
from typing import Any, Optional
from threading import Lock

class TTLCache:
    def __init__(self):
        self._cache = {}
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._cache.get(key)
            if entry and time.time() < entry['expires']:
                return entry['value']
            if entry:
                del self._cache[key]
            return None

    def set(self, key: str, value: Any, ttl: int = 30):
        with self._lock:
            self._cache[key] = {'value': value, 'expires': time.time() + ttl}

    def delete(self, key: str):
        with self._lock:
            self._cache.pop(key, None)

    def clear_prefix(self, prefix: str):
        with self._lock:
            keys = [k for k in self._cache if k.startswith(prefix)]
            for k in keys:
                del self._cache[k]

    def clear(self):
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()

    def stats(self) -> dict:
        """Return cache statistics: size and list of non-expired keys."""
        with self._lock:
            now = time.time()
            live_keys = [k for k, v in self._cache.items() if now < v['expires']]
            return {
                "size": len(live_keys),
                "total_entries": len(self._cache),
                "keys": live_keys,
            }

pve_cache = TTLCache()
