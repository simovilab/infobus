from runs.events.types import OccupancyStatusChanged, RunLifecycleEvent

from updates.topics import TopicKey


def resolve_trip_occupancy_topics(
    event: OccupancyStatusChanged | RunLifecycleEvent,
) -> list[TopicKey]:
    return [
        TopicKey(
            transit_system=event.transit_system,
            entity="trip",
            info="occupancy_status",
            primary_selector="by_run",
            primary_value=str(event.run_id),
        )
    ]
