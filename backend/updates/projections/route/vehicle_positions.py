from runs.events.types import RunLifecycleEvent
from runs.models import Run

from updates.directions import direction_id_from_topic
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


def validate_vehicle_positions_by_direction_topic(topic: TopicKey) -> None:
    """Validate the route ID and direction required by the qualified projection."""
    if not topic.primary_value:
        raise InvalidTopicException(topic.render(), "route_id cannot be empty.")
    direction_id_from_topic(topic)


def resolve_vehicle_positions_by_direction_topics(
    event: RunLifecycleEvent,
) -> list[TopicKey]:
    """Resolve a lifecycle invalidation to the run's route-and-direction topic."""
    row = (
        Run.objects.filter(
            id=event.run_id,
            feed_publisher__transit_system__code=event.transit_system,
        )
        .values_list("route_id", "direction_id")
        .first()
    )
    if row is None:
        return []

    route_id, direction_id = row
    if route_id is None or route_id == "":
        return []
    if direction_id not in (0, 1):
        return []

    return [
        TopicKey(
            transit_system=event.transit_system,
            entity="route",
            info="vehicle_positions",
            primary_selector="by_route",
            primary_value=str(route_id),
            qualifier_selector="by_direction",
            qualifier_value=str(direction_id),
        )
    ]
