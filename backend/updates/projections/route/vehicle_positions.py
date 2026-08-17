from runs.events.types import RunLifecycleEvent
from runs.models import Run

from updates.exceptions import InvalidTopicException
from updates.topics import TopicKey


def validate_vehicle_positions_topic(topic: TopicKey) -> None:
    """Validate the route ID required by the vehicle-position projection."""
    if not topic.primary_value:
        raise InvalidTopicException(topic.render(), "route_id cannot be empty.")


def resolve_vehicle_positions_topics(
    event: RunLifecycleEvent,
) -> list[TopicKey]:
    """Resolve a lifecycle invalidation to the run's route topic."""
    route_id = (
        Run.objects.filter(
            id=event.run_id,
            feed_publisher__transit_system__code=event.transit_system,
        )
        .values_list("route_id", flat=True)
        .first()
    )
    if route_id is None or route_id == "":
        return []

    return [
        TopicKey(
            transit_system=event.transit_system,
            entity="route",
            info="vehicle_positions",
            primary_selector="by_route",
            primary_value=str(route_id),
        )
    ]
