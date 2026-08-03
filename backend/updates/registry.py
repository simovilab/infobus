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

from .builders.stop.occupancy_status import build_stop_occupancy_status
from .builders.trip.occupancy_status import build_trip_occupancy_status
from .events import UpdateEvent
from .projections.stop.occupancy_status import resolve_stop_occupancy_topics
from .projections.trip.occupancy_status import resolve_trip_occupancy_topics
from .topics import TopicKey, TopicPattern


Snapshot: TypeAlias = dict[str, object]
TopicResolver: TypeAlias = Callable[[UpdateEvent], list[TopicKey]]
SnapshotBuilder: TypeAlias = Callable[[TopicKey], Snapshot | None]


@dataclass(frozen=True)
class ProjectionSpec:
    """Describe how events invalidate and rebuild one topic projection."""

    name: str
    description: str
    topic_pattern: TopicPattern
    triggers: tuple[type[Event], ...]
    resolve_topics: TopicResolver
    build: SnapshotBuilder


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
