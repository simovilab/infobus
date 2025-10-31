from __future__ import annotations

from typing import List, Optional, Protocol, TypedDict, runtime_checkable
from datetime import date, time


class Departure(TypedDict):
    route_id: str
    route_short_name: Optional[str]
    route_long_name: Optional[str]
    trip_id: str
    stop_id: str
    headsign: Optional[str]
    direction_id: Optional[int]
    arrival_time: Optional[str]  # HH:MM:SS
    departure_time: Optional[str]  # HH:MM:SS


@runtime_checkable
class ScheduleRepository(Protocol):
    """Abstract interface for reading scheduled service information."""

    def get_next_departures(
        self,
        *,
        feed_id: str,
        stop_id: str,
        service_date: date,
        from_time: time,
        limit: int = 10,
    ) -> List[Departure]:
        """Return the next scheduled departures at a stop.

        Notes:
        - Implementations may approximate service availability and ignore
          service_date exceptions initially; exact filtering can be added later.
        """
        ...


@runtime_checkable
class CacheProvider(Protocol):
    def get(self, key: str) -> Optional[str]:
        ...

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        ...
