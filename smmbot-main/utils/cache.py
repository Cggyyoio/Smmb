"""
🗄️ كاش الخدمات — utils/cache.py
"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 دقائق


class ServicesCache:
    def __init__(self):
        self._data: dict   = {}   # key → (value, expires_at)

    def get(self, key: str):
        item = self._data.get(key)
        if item and time.time() < item[1]:
            return item[0]
        if key in self._data:
            del self._data[key]
        return None

    def set(self, key: str, value, ttl: int = _CACHE_TTL):
        self._data[key] = (value, time.time() + ttl)

    def invalidate(self, key: str = None):
        if key:
            self._data.pop(key, None)
        else:
            self._data.clear()

    def get_platforms(self, db, active_only=True):
        key = f"platforms_{active_only}"
        cached = self.get(key)
        if cached is not None:
            return cached
        result = db.get_platforms(active_only=active_only)
        self.set(key, result)
        return result

    def get_categories(self, db, platform_id: int, active_only=True):
        key = f"cats_{platform_id}_{active_only}"
        cached = self.get(key)
        if cached is not None:
            return cached
        result = db.get_categories(platform_id, active_only=active_only)
        self.set(key, result)
        return result

    def get_services(self, db, category_id: int, active_only=True):
        key = f"svcs_{category_id}_{active_only}"
        cached = self.get(key)
        if cached is not None:
            return cached
        result = db.get_services(category_id, active_only=active_only)
        self.set(key, result)
        return result


# Singleton
_cache = ServicesCache()


def get_cache() -> ServicesCache:
    return _cache
