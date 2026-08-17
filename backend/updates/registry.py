from dataclasses import dataclass
from collections.abc import Callable
from typing import TypeAlias

from runs.events.types import (
    Event,
    OccupancyStatusChanged,
    RunCancelled,
    RunCompleted,
    RunInterrupted,
    RunSignalLost,
    RunSignalRestored,
)

from .builders.route.vehicle_positions import build_route_vehicle_positions
from .builders.stop.occupancy_status import build_stop_occupancy_status
from .builders.stop.stop_time_updates import build_stop_time_updates
from .builders.trip.occupancy_status import build_trip_occupancy_status
from .events import UpdateEvent
from .projections.route.vehicle_positions import (
    resolve_vehicle_positions_topics,
    validate_vehicle_positions_topic,
)
from .projections.stop.occupancy_status import resolve_stop_occupancy_topics
from .projections.stop.stop_time_updates import (
    resolve_stop_time_updates_topics,
    validate_stop_time_updates_topic,
)
from .projections.trip.occupancy_status import resolve_trip_occupancy_topics
from .topics import TopicKey, TopicPattern


Snapshot: TypeAlias = dict[str, object]
TopicResolver: TypeAlias = Callable[[UpdateEvent], list[TopicKey]]
SnapshotBuilder: TypeAlias = Callable[[TopicKey], Snapshot | None]
TopicValidator: TypeAlias = Callable[[TopicKey], None]


@dataclass(frozen=True)
class ProjectionSpec:
    """Describe how events invalidate and rebuild one topic projection."""

    name: str
    description: str
    topic_pattern: TopicPattern
    triggers: tuple[type[Event], ...]
    resolve_topics: TopicResolver
    build: SnapshotBuilder
    validate_topic: TopicValidator | None = None


PROJECTIONS = (
    ProjectionSpec(
        name="trip_occupancy_status",
        description="The occupancy status of a trip, by run ID.",
        topic_pattern=TopicPattern(
            entity="trip",
            info="occupancy_status",
            primary_selector="by_run",
        ),
        triggers=(
            OccupancyStatusChanged,
            RunSignalLost,
            RunSignalRestored,
            RunCompleted,
            RunInterrupted,
            RunCancelled,
        ),
        resolve_topics=resolve_trip_occupancy_topics,
        build=build_trip_occupancy_status,
    ),
    ProjectionSpec(
        name="stop_occupancy_status",
        description="The occupancy status of the trips coming to a stop, by stop ID.",
        topic_pattern=TopicPattern(
            entity="stop",
            info="occupancy_status",
            primary_selector="by_stop",
        ),
        triggers=(
            OccupancyStatusChanged,
            RunSignalLost,
            RunSignalRestored,
            RunCompleted,
            RunInterrupted,
            RunCancelled,
        ),
        resolve_topics=resolve_stop_occupancy_topics,
        build=build_stop_occupancy_status,
    ),
    ProjectionSpec(
        name="stop_stop_time_updates",
        description=(
            "The current stop-time predictions for runs coming to a stop, "
            "by stop ID and GTFS direction ID."
        ),
        topic_pattern=TopicPattern(
            entity="stop",
            info="stop_time_updates",
            primary_selector="by_stop",
            qualifier_selector="by_direction",
        ),
        triggers=(
            RunSignalLost,
            RunSignalRestored,
            RunCompleted,
            RunInterrupted,
            RunCancelled,
        ),
        resolve_topics=resolve_stop_time_updates_topics,
        build=build_stop_time_updates,
        validate_topic=validate_stop_time_updates_topic,
    ),
    ProjectionSpec(
        name="route_vehicle_positions",
        description=(
            "The current vehicle positions for active runs on a route, "
            "by route ID."
        ),
        topic_pattern=TopicPattern(
            entity="route",
            info="vehicle_positions",
            primary_selector="by_route",
        ),
        triggers=(
            RunSignalLost,
            RunSignalRestored,
            RunCompleted,
            RunInterrupted,
            RunCancelled,
        ),
        resolve_topics=resolve_vehicle_positions_topics,
        build=build_route_vehicle_positions,
        validate_topic=validate_vehicle_positions_topic,
    ),
)


def projections_for_event(event: UpdateEvent) -> tuple[ProjectionSpec, ...]:
    """Return every projection triggered by an event."""
    return tuple(
        projection
        for projection in PROJECTIONS
        if isinstance(event, projection.triggers)
    )


def projection_for_topic(topic: TopicKey) -> ProjectionSpec | None:
    """Return the projection registered for a concrete topic, if any."""
    return next(
        (
            projection
            for projection in PROJECTIONS
            if projection.topic_pattern.matches(topic)
        ),
        None,
    )
