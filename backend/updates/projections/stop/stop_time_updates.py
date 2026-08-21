import json

from runs.events.types import RunLifecycleEvent
from runs.models import Run

from updates.directions import direction_id_from_topic
from updates.exceptions import InvalidTopicException
from updates.topics import TopicKey


def validate_stop_time_updates_topic(topic: TopicKey) -> None:
    """Validate the semantic values required by the stop-time projection."""
    if not topic.primary_value:
        raise InvalidTopicException(topic.render(), "stop_id cannot be empty.")
    direction_id_from_topic(topic)


def resolve_stop_time_updates_topics(
    event: RunLifecycleEvent,
) -> list[TopicKey]:
    """Resolve lifecycle invalidations using captured stops and Run direction."""
    direction_id = (
        Run.objects.filter(
            id=event.run_id,
            feed_publisher__transit_system__code=event.transit_system,
        )
        .values_list("direction_id", flat=True)
        .first()
    )
    if direction_id not in (0, 1):
        return []

    try:
        raw_stop_ids = json.loads(event.affected_stop_ids_json or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(raw_stop_ids, list):
        return []

    stop_ids = list(
        dict.fromkeys(str(stop_id) for stop_id in raw_stop_ids if str(stop_id))
    )
    return [
        TopicKey(
            transit_system=event.transit_system,
            entity="stop",
            info="stop_time_updates",
            primary_selector="by_stop",
            primary_value=stop_id,
            qualifier_selector="by_direction",
            qualifier_value=str(direction_id),
        )
        for stop_id in stop_ids
    ]
