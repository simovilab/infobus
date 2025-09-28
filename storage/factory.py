from __future__ import annotations

from datetime import date, time
from typing import List

from django.conf import settings

from .cached_schedule import CachedScheduleRepository
from .interfaces import ScheduleRepository
from .postgres_schedule import PostgresScheduleRepository
from .redis_cache import RedisCacheProvider
from .fuseki_schedule import FusekiScheduleRepository


def get_schedule_repository(*, use_cache: bool = True) -> ScheduleRepository:
    """Factory to obtain a ScheduleRepository according to settings.

    - Uses PostgreSQL (Django ORM) by default.
    - Optionally wraps with Redis cache.
    - If FUSEKI_ENABLED is true and endpoint configured, uses Fuseki adapter instead.
    """
    base_repo: ScheduleRepository
    if getattr(settings, "FUSEKI_ENABLED", False) and getattr(settings, "FUSEKI_ENDPOINT", None):
        base_repo = FusekiScheduleRepository(endpoint=settings.FUSEKI_ENDPOINT)  # type: ignore[arg-type]
    else:
        base_repo = PostgresScheduleRepository()

    if use_cache:
        cache = RedisCacheProvider()
        return CachedScheduleRepository(base_repo, cache)
    return base_repo
