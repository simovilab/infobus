from __future__ import annotations

import json
from typing import Optional

from django.conf import settings
import redis

from .interfaces import CacheProvider


class RedisCacheProvider(CacheProvider):
    """Simple Redis-backed cache for DAL results.

    Stores JSON-encoded strings under namespaced keys.
    """

    def __init__(self, *, host: Optional[str] = None, port: Optional[int] = None):
        self._host = host or settings.REDIS_HOST
        self._port = int(port or settings.REDIS_PORT)
        # decode_responses=True to work with str values
        self._client = redis.Redis(host=self._host, port=self._port, decode_responses=True)

    def get(self, key: str) -> Optional[str]:
        try:
            return self._client.get(key)
        except Exception:
            # Cache failures should not break the application
            return None

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        try:
            self._client.setex(key, ttl_seconds, value)
        except Exception:
            # Best-effort cache set
            pass
