import json

from runs.events.types import OccupancyStatusChanged, RunLifecycleEvent
from runs.services.stop_index import remaining_stop_ids

from updates.topics import TopicKey


def resolve_stop_occupancy_topics(
    event: OccupancyStatusChanged | RunLifecycleEvent,
) -> list[TopicKey]:
    if isinstance(event, RunLifecycleEvent):
        stop_ids = json.loads(event.affected_stop_ids_json or "[]")
    else:
        stop_ids = remaining_stop_ids(event.transit_system, event.run_id)
    return [
        TopicKey(
            transit_system=event.transit_system,
            entity="stop",
            info="occupancy_status",
            primary_selector="by_stop",
            primary_value=stop_id,
        )
        for stop_id in stop_ids
    ]
