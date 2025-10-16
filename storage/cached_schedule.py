from __future__ import annotations

import json
from datetime import date, time
from typing import List

from .interfaces import CacheProvider, Departure, ScheduleRepository


class CachedScheduleRepository(ScheduleRepository):
    """Cache wrapper for any ScheduleRepository.

    Keys are namespaced to avoid collisions and include parameters for safety.
    """

    def __init__(self, repo: ScheduleRepository, cache: CacheProvider, *, ttl_seconds: int = 60):
        self._repo = repo
        self._cache = cache
        self._ttl = ttl_seconds

    @staticmethod
    def _key(*, feed_id: str, stop_id: str, service_date: date, from_time: time, limit: int) -> str:
        return (
            f"schedule:next_departures:feed={feed_id}:stop={stop_id}:"
            f"date={service_date.isoformat()}:time={from_time.strftime('%H%M%S')}:limit={limit}:v1"
        )

    def get_next_departures(
        self,
        *,
        feed_id: str,
        stop_id: str,
        service_date: date,
        from_time: time,
        limit: int = 10,
    ) -> List[Departure]:
        key = self._key(
            feed_id=feed_id,
            stop_id=stop_id,
            service_date=service_date,
            from_time=from_time,
            limit=limit,
        )
        cached = self._cache.get(key)
        if cached:
            try:
                return json.loads(cached)
            except Exception:
                # Fallback to fetching from source if cache content is invalid
                pass

        result = self._repo.get_next_departures(
            feed_id=feed_id,
            stop_id=stop_id,
            service_date=service_date,
            from_time=from_time,
            limit=limit,
        )
        try:
            self._cache.set(key, json.dumps(result), self._ttl)
        except Exception:
            pass
        return result
