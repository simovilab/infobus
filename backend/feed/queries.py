import pytz
from django.conf import settings
from datetime import datetime, timedelta
from .models import (
    Feed,
    Calendar,
    CalendarDate,
    FeedMessage,
    StopTimeUpdate,
    TripUpdate,
    Trip,
    Route,
    VehiclePosition,
    GeoShape,
    StopTime,
)
from api.serializers import NextTripSerializer
from shapely import geometry


def get_calendar(date, current_feed):
    """Get the service_id for the specified date."""
    exception_type = 1  # Service has been added for the specified date.
    exception = CalendarDate.objects.filter(
        feed=current_feed, date=date, exception_type=exception_type
    ).first()

    if exception:
        service_id = exception.service_id
    else:
        day_of_week = date.strftime("%A").lower()
        kwargs = {"feed": current_feed, day_of_week: True}
        calendar = Calendar.objects.filter(**kwargs).first()
        if not calendar:
            service_id = None
        else:
            service_id = calendar.service_id

    return service_id


def get_next_trips(transit_system, stop_id, timestamp=None):
    """
    Core logic for fetching next trips for a stop.

    Returns the serialized data dict, or None if no service is available for
    the given date. Raises Stop.DoesNotExist if the stop is not found.
    """
    tz = pytz.timezone(settings.TIME_ZONE)

    if timestamp is None:
        timestamp = tz.localize(datetime.now())

    # Get the current GTFS feed
    current_feed = Feed.objects.filter(
        transit_system=transit_system, is_current=True
    ).latest("retrieved_at")
    service_id = get_calendar(timestamp.date(), current_feed)
    if service_id is None:
        return None

    next_arrivals = []

    # -----------------
    # Trips in progress, TODO: get everything from Redis
    # -----------------

    latest_feed_message = (
        FeedMessage.objects.filter(entity_type="trip_update")
        .order_by("-timestamp")
        .first()
    )
    # TODO: check TTL (time to live)
    if latest_feed_message is None:
        # No realtime messages available; keep trips_in_progress empty
        stop_time_updates = StopTimeUpdate.objects.none()
    else:
        stop_time_updates = StopTimeUpdate.objects.filter(
            trip_update__feed_message=latest_feed_message, stop_id=stop_id
        )

    trips_in_progress = []  # runs:in_progress

    # Build the response for trips in progress
    for stop_time_update in stop_time_updates:
        trip_update = TripUpdate.objects.get(
            id=stop_time_update.trip_update.id,
        )
        trip = Trip.objects.filter(
            trip_id=trip_update.trip_trip_id, feed=current_feed
        ).first()
        trips_in_progress.append(trip)
        route = Route.objects.filter(route_id=trip.route_id, feed=current_feed).first()
        vehicle_position = VehiclePosition.objects.filter(
            # TODO: ponder if making a new table for TripDescriptor is better
            vehicle_trip_trip_id=trip_update.trip_trip_id,
            vehicle_trip_start_date=trip_update.trip_start_date,
            vehicle_trip_start_time=trip_update.trip_start_time,
        ).first()
        geo_shape = GeoShape.objects.filter(
            shape_id=trip.shape_id, feed=current_feed
        ).first()
        geo_shape = geometry.LineString(geo_shape.geometry.coords)
        location = vehicle_position.vehicle_position_point
        location = geometry.Point(location.x, location.y)
        position_in_shape = geo_shape.project(location) / geo_shape.length

        next_arrivals.append(
            {
                "trip_id": trip.trip_id,
                "route_id": route.route_id,
                "route_short_name": route.route_short_name,
                "route_long_name": route.route_long_name,
                "trip_headsign": trip.trip_headsign,
                "wheelchair_accessible": trip.wheelchair_accessible,
                "arrival_time": stop_time_update.arrival_time,
                "departure_time": stop_time_update.departure_time,
                "in_progress": True,
                "progression": {
                    "position_in_shape": position_in_shape,
                    "current_stop_sequence": vehicle_position.vehicle_current_stop_sequence,
                    "current_status": vehicle_position.vehicle_current_status,
                    "occupancy_status": vehicle_position.vehicle_occupancy_status,
                },
            }
        )

    # ---------------
    # Scheduled trips
    # ---------------

    t = timestamp
    time_as_duration = timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)

    stop_times = StopTime.objects.filter(
        feed=current_feed,
        stop_id=stop_id,
        arrival_time__gte=time_as_duration,
        arrival_time__lte=timedelta(hours=5) + time_as_duration,
        # _trip__service_id=service_id,
    ).order_by("arrival_time")

    print(f"Stop: {stop_id}, feed: {current_feed.feed_id}, Stop times: {stop_times}")

    # Build the response for scheduled trips
    for stop_time in stop_times:
        trip = Trip.objects.filter(trip_id=stop_time.trip_id, feed=current_feed).first()
        if trip in trips_in_progress:
            continue
        route = Route.objects.filter(route_id=trip.route_id, feed=current_feed).first()

        midnight = datetime.combine(timestamp.date(), datetime.min.time())
        arrival_time = tz.localize(midnight + stop_time.arrival_time)
        departure_time = tz.localize(midnight + stop_time.departure_time)

        next_arrivals.append(
            {
                "trip_id": trip.trip_id,
                "route_id": route.route_id,
                "route_short_name": route.route_short_name,
                "route_long_name": route.route_long_name,
                "trip_headsign": trip.trip_headsign,
                "wheelchair_accessible": trip.wheelchair_accessible,
                "arrival_time": arrival_time,
                "departure_time": departure_time,
                "in_progress": False,
                "progression": None,
            }
        )

    # Sort the list by arrival time
    next_arrivals.sort(key=lambda x: x["arrival_time"])

    data = {
        "stop_id": stop_id,
        "timestamp": timestamp,
        "next_arrivals": next_arrivals,
    }

    serializer = NextTripSerializer(data)
    return serializer.data
