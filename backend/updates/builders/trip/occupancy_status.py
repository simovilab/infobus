from django.conf import settings
from redis import Redis
from runs.models import Run

from updates.topics import TopicKey


r = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_CELERY_DB,
    decode_responses=True,
)


def build_trip_occupancy_status(topic: TopicKey) -> dict | None:
    """Assemble a trip-topic payload from persisted run metadata and its Redis occupancy state."""
    run_id = topic.primary_value
    run = Run.objects.filter(
        id=run_id,
        feed_publisher__transit_system__code=topic.transit_system,
    ).first()
    if run is None:
        return None
    occupancy_status = r.get(f"{topic.transit_system}:trip:{run_id}:occupancy_status")
    if occupancy_status is None:
        return None

    return {
        "topic": topic.render(),
        "run_id": run_id,
        "trip_id": run.trip_id,
        "route_id": run.route_id,
        "occupancy_status": (
            int(occupancy_status) if occupancy_status is not None else None
        ),
        "lifecycle_state": run.run_lifecycle_state,
    }
