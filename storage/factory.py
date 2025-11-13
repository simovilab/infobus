from __future__ import annotations

from datetime import date, time
from typing import List

from django.conf import settings

from .cached_schedule import CachedScheduleRepository
from .interfaces import ScheduleRepository
from .postgres_schedule import PostgresScheduleRepository
from .redis_cache import RedisCacheProvider


def get_schedule_repository(*, use_cache: bool = True) -> ScheduleRepository:
    """Factory to obtain a ScheduleRepository according to settings.

    - Uses PostgreSQL (Django ORM) by default.
    - Optionally wraps with Redis cache for improved performance.
    """
    base_repo: ScheduleRepository = PostgresScheduleRepository()

    if use_cache:
        cache = RedisCacheProvider()
        ttl = getattr(settings, "SCHEDULE_CACHE_TTL_SECONDS", 60)
        return CachedScheduleRepository(base_repo, cache, ttl_seconds=int(ttl))
    return base_repo
