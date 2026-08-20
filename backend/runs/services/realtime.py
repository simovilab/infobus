from uuid import UUID

from django.conf import settings
from feed.models import FeedPublisher
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from runs.models import Run
from gtfs.utils import gtfs_date, gtfs_time
from redis import Redis

r = Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_CELERY_DB
)


def confirm_run_record(
    feed_publisher: FeedPublisher,
    trip: gtfs_rt.TripDescriptor,
) -> Run:
    """Return the run confirmed from a GTFS descriptor and sync its metadata."""
    schedule_relationship = None
    if trip.HasField("schedule_relationship"):
        enum_type = trip.DESCRIPTOR.fields_by_name["schedule_relationship"].enum_type
        schedule_relationship = enum_type.values_by_number[
            trip.schedule_relationship
        ].name

    trip_descriptor = {
        "trip_id": trip.trip_id if trip.HasField("trip_id") else None,
        "route_id": trip.route_id if trip.HasField("route_id") else None,
        "direction_id": trip.direction_id if trip.HasField("direction_id") else None,
        "schedule_relationship": schedule_relationship,
        "start_time": gtfs_time(trip.start_time)
        if trip.HasField("start_time")
        else None,
        "start_date": gtfs_date(trip.start_date)
        if trip.HasField("start_date")
        else None,
    }
    redis_trip_descriptor = {
        field: value if isinstance(value, (bytes, str, int, float)) else str(value)
        for field, value in trip_descriptor.items()
        if value is not None
    }

    filters = {
        "feed_publisher": feed_publisher,
    }
    if trip.HasField("trip_id"):
        filters["trip_id"] = trip.trip_id
    if trip.HasField("start_date"):
        filters["start_date"] = gtfs_date(trip.start_date)
    if trip.HasField("start_time"):
        filters["start_time"] = gtfs_time(trip.start_time)
    run = Run.objects.filter(**filters).first()

    if run:
        fields_to_update = []
        for field in ("route_id", "direction_id", "schedule_relationship"):
            value = trip_descriptor[field]
            if value is not None and getattr(run, field) != value:
                setattr(run, field, value)
                fields_to_update.append(field)
        if fields_to_update:
            run.save(update_fields=fields_to_update)

        # If the run already exists, confirm its metadata is in Redis
        if redis_trip_descriptor and not r.hexists(f"trip:{run.id}:trip", "trip_id"):
            r.hset(
                f"trip:{run.id}:trip",
                mapping=redis_trip_descriptor,
            )
    else:
        # If the run does not exist, create it in the database
        run = Run.objects.create(
            feed_publisher=feed_publisher,
            trip_id=trip_descriptor["trip_id"],
            route_id=trip_descriptor["route_id"],
            direction_id=trip_descriptor["direction_id"],
            start_date=trip_descriptor["start_date"],
            start_time=trip_descriptor["start_time"],
            schedule_relationship=trip_descriptor["schedule_relationship"],
        )
        # Create the metadata hash for the run in Redis
        if redis_trip_descriptor:
            r.hset(
                f"trip:{run.id}:trip",
                mapping=redis_trip_descriptor,
            )
    return run


def confirm_run(
    feed_publisher: FeedPublisher,
    trip: gtfs_rt.TripDescriptor,
) -> UUID:
    """Return the UUID confirmed from a GTFS trip descriptor."""
    return confirm_run_record(feed_publisher, trip).id
