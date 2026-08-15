from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


DirectionID = Literal[0, 1]
StopTimeScheduleRelationship = Literal[
    "SCHEDULED",
    "SKIPPED",
    "NO_DATA",
    "UNSCHEDULED",
]


class StopTimeEventSnapshot(BaseModel):
    """Represent the current GTFS Realtime prediction for one stop event."""

    model_config = ConfigDict(extra="forbid")

    delay: int | None = None
    time: int | None = None
    uncertainty: int | None = None


class StopTimeUpdateSnapshot(BaseModel):
    """Represent one run's current prediction for one visit to a stop."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    trip_id: str | None
    route_id: str | None
    direction_id: DirectionID
    stop_id: str
    stop_sequence: int | None
    arrival: StopTimeEventSnapshot
    departure: StopTimeEventSnapshot
    schedule_relationship: StopTimeScheduleRelationship | None = None


class StopTimeUpdatesByStopSnapshot(BaseModel):
    """Represent the complete current prediction list for a stop and direction."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    stop_id: str
    direction_id: DirectionID
    stop_time_updates: list[StopTimeUpdateSnapshot]
