from datetime import datetime
from enum import IntEnum
from typing import Literal
from uuid import UUID, uuid7

from pydantic import BaseModel, ConfigDict, Field


class VehicleStopStatus(IntEnum):
    INCOMING_AT = 0
    STOPPED_AT = 1
    IN_TRANSIT_TO = 2


class CongestionLevel(IntEnum):
    UNKNOWN_CONGESTION_LEVEL = 0
    RUNNING_SMOOTHLY = 1
    STOP_AND_GO = 2
    CONGESTION = 3
    SEVERE_CONGESTION = 4


class OccupancyStatus(IntEnum):
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
    model_config = ConfigDict(frozen=True, extra="forbid")

    transit_system: str
    event_id: UUID = Field(default_factory=uuid7)
    event_type: str
    run_id: UUID

    def redis_fields(self):
        return self.model_dump(mode="json", exclude_none=True)


class CurrentStopSequenceChanged(Event):
    event_type: Literal["CurrentStopSequenceChanged"] = "CurrentStopSequenceChanged"
    previous_state: int | None = None
    current_state: int


class StopIDChanged(Event):
    event_type: Literal["StopIDChanged"] = "StopIDChanged"
    previous_state: str | None = None
    current_state: str


class CurrentStatusChanged(Event):
    event_type: Literal["CurrentStatusChanged"] = "CurrentStatusChanged"
    previous_state: VehicleStopStatus | None = None
    current_state: VehicleStopStatus


class CongestionLevelChanged(Event):
    event_type: Literal["CongestionLevelChanged"] = "CongestionLevelChanged"
    previous_state: CongestionLevel | None = None
    current_state: CongestionLevel


class OccupancyStatusChanged(Event):
    event_type: Literal["OccupancyStatusChanged"] = "OccupancyStatusChanged"
    previous_state: OccupancyStatus | None = None
    current_state: OccupancyStatus


class OccupancyPercentageChanged(Event):
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
    event_type: Literal["RunSignalLost"] = "RunSignalLost"


class RunSignalRestored(RunLifecycleEvent):
    event_type: Literal["RunSignalRestored"] = "RunSignalRestored"


class RunCompleted(RunLifecycleEvent):
    event_type: Literal["RunCompleted"] = "RunCompleted"


class RunInterrupted(RunLifecycleEvent):
    event_type: Literal["RunInterrupted"] = "RunInterrupted"


class RunCancelled(RunLifecycleEvent):
    event_type: Literal["RunCancelled"] = "RunCancelled"
