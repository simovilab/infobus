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


class VehiclePositionSnapshot(BaseModel):
    """Represent one active run's current GTFS Realtime vehicle position."""

    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    trip_id: str | None
    route_id: str
    direction_id: int | None
    latitude: float
    longitude: float
    bearing: float | None
    speed: float | None
    odometer: float | None
    current_stop_sequence: int | None
    stop_id: str | None
    current_status: int | None
    congestion_level: int | None
    occupancy_status: int | None
    occupancy_percentage: int | None
    timestamp: int | None


class VehiclePositionsByRouteSnapshot(BaseModel):
    """Represent all current vehicle positions for one route."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    route_id: str
    vehicles: list[VehiclePositionSnapshot]
