from datetime import datetime
from enum import IntEnum
from typing import Literal
from uuid import UUID, uuid7

from pydantic import BaseModel, ConfigDict, Field


class VehicleStopStatus(IntEnum):
    """Enumerate a vehicle's relationship to its reported stop."""

    INCOMING_AT = 0
    STOPPED_AT = 1
    IN_TRANSIT_TO = 2


class CongestionLevel(IntEnum):
    """Enumerate the traffic conditions available in vehicle-position updates."""

    UNKNOWN_CONGESTION_LEVEL = 0
    RUNNING_SMOOTHLY = 1
    STOP_AND_GO = 2
    CONGESTION = 3
    SEVERE_CONGESTION = 4


class OccupancyStatus(IntEnum):
    """Enumerate passenger-capacity conditions available in vehicle-position updates."""

    EMPTY = 0
    MANY_SEATS_AVAILABLE = 1
    FEW_SEATS_AVAILABLE = 2
    STANDING_ROOM_ONLY = 3
    CRUSHED_STANDING_ROOM_ONLY = 4
    FULL = 5
    NOT_ACCEPTING_PASSENGERS = 6
    NO_DATA_AVAILABLE = 7
    NOT_BOARDABLE = 8


class Event(BaseModel):
    """Define the publisher, run, and state-transition fields shared by every typed run event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    transit_system: str
    event_id: UUID = Field(default_factory=uuid7)
    event_type: str
    run_id: UUID

    def redis_fields(self) -> dict[str, object]:
        """Serialize an event as JSON-compatible Redis fields while omitting null values."""
        return self.model_dump(mode="json", exclude_none=True)


class CurrentStopSequenceChanged(Event):
    """Carry the previous and current stop sequences for a discriminated run event."""

    event_type: Literal["CurrentStopSequenceChanged"] = "CurrentStopSequenceChanged"
    previous_state: int | None = None
    current_state: int


class StopIDChanged(Event):
    """Carry the previous and current stop identifiers for a discriminated run event."""

    event_type: Literal["StopIDChanged"] = "StopIDChanged"
    previous_state: str | None = None
    current_state: str


class CurrentStatusChanged(Event):
    """Carry the previous and current vehicle stop statuses for a discriminated run event."""

    event_type: Literal["CurrentStatusChanged"] = "CurrentStatusChanged"
    previous_state: VehicleStopStatus | None = None
    current_state: VehicleStopStatus


class CongestionLevelChanged(Event):
    """Carry the previous and current congestion levels for a discriminated run event."""

    event_type: Literal["CongestionLevelChanged"] = "CongestionLevelChanged"
    previous_state: CongestionLevel | None = None
    current_state: CongestionLevel


class OccupancyStatusChanged(Event):
    """Carry the previous and current occupancy statuses for a discriminated run event."""

    event_type: Literal["OccupancyStatusChanged"] = "OccupancyStatusChanged"
    previous_state: OccupancyStatus | None = None
    current_state: OccupancyStatus


class OccupancyPercentageChanged(Event):
    """Carry the previous and current occupancy percentages for a discriminated run event."""

    event_type: Literal["OccupancyPercentageChanged"] = "OccupancyPercentageChanged"
    previous_state: int | None = None
    current_state: int


class RunLifecycleEvent(Event):
    """Describe a persisted transition in a run's lifecycle."""

    reason: str
    occurred_at: datetime
    last_seen_at: datetime | None = None
    affected_stop_ids_json: str | None = None


class RunSignalLost(RunLifecycleEvent):
    """Supply the event discriminator for lifecycle transitions into the no-signal state."""

    event_type: Literal["RunSignalLost"] = "RunSignalLost"


class RunSignalRestored(RunLifecycleEvent):
    """Supply the event discriminator for transitions back to in-progress after signal recovery."""

    event_type: Literal["RunSignalRestored"] = "RunSignalRestored"


class RunCompleted(RunLifecycleEvent):
    """Supply the event discriminator for transitions into the completed terminal state."""

    event_type: Literal["RunCompleted"] = "RunCompleted"


class RunInterrupted(RunLifecycleEvent):
    """Supply the event discriminator for transitions into the interrupted terminal state."""

    event_type: Literal["RunInterrupted"] = "RunInterrupted"


class RunCancelled(RunLifecycleEvent):
    """Supply the event discriminator for transitions into the cancelled terminal state."""

    event_type: Literal["RunCancelled"] = "RunCancelled"
