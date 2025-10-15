from __future__ import annotations

from datetime import date, time
from typing import List

from django.db.models import F

from gtfs.models import StopTime, Trip, Route
from .interfaces import Departure, ScheduleRepository


class PostgresScheduleRepository(ScheduleRepository):
    """PostgreSQL-backed schedule repository using Django ORM.

    NOTE: This initial implementation does not yet filter by service_date
    (Calendar/CalendarDate). That logic can be layered in a future iteration.
    """

    def get_next_departures(
        self,
        *,
        feed_id: str,
        stop_id: str,
        service_date: date,
        from_time: time,
        limit: int = 10,
    ) -> List[Departure]:
        qs = (
            StopTime.objects.select_related("_trip")
            .filter(
                feed__feed_id=feed_id,
                stop_id=stop_id,
                departure_time__isnull=False,
                departure_time__gte=from_time,
            )
            .order_by("departure_time")
        )
        qs = qs[:limit]

        results: List[Departure] = []
        for st in qs:
            # Ensure we can resolve the Trip, even if _trip is not populated
            trip: Trip | None = getattr(st, "_trip", None)  # type: ignore
            if trip is None:
                trip = Trip.objects.filter(feed=st.feed, trip_id=st.trip_id).first()

            route_id_val = trip.route_id if trip else ""
            route_short_name = None
            route_long_name = None
            if route_id_val:
                route = Route.objects.filter(feed=st.feed, route_id=route_id_val).only(
                    "route_short_name", "route_long_name"
                ).first()
                if route is not None:
                    route_short_name = route.route_short_name
                    route_long_name = route.route_long_name

            results.append(
                {
                    "route_id": route_id_val,
                    "route_short_name": route_short_name,
                    "route_long_name": route_long_name,
                    "trip_id": st.trip_id,
                    "stop_id": st.stop_id,
                    "headsign": getattr(trip, "trip_headsign", None) if trip else None,
                    "direction_id": getattr(trip, "direction_id", None) if trip else None,
                    "arrival_time": st.arrival_time.strftime("%H:%M:%S") if st.arrival_time else None,
                    "departure_time": st.departure_time.strftime("%H:%M:%S") if st.departure_time else None,
                }
            )
        return results
