from typing import Annotated

from pydantic import Field, TypeAdapter
from runs.events.types import (
    CongestionLevelChanged,
    CurrentStatusChanged,
    CurrentStopSequenceChanged,
    OccupancyPercentageChanged,
    OccupancyStatusChanged,
    RunCancelled,
    RunCompleted,
    RunInterrupted,
    RunSignalLost,
    RunSignalRestored,
    StopIDChanged,
)


UpdateEvent = Annotated[
    CurrentStopSequenceChanged
    | StopIDChanged
    | CurrentStatusChanged
    | CongestionLevelChanged
    | OccupancyStatusChanged
    | OccupancyPercentageChanged
    | RunSignalLost
    | RunSignalRestored
    | RunCompleted
    | RunInterrupted
    | RunCancelled,
    Field(discriminator="event_type"),
]

_event_adapter = TypeAdapter(UpdateEvent)


def parse_event(fields: dict[str, str]) -> UpdateEvent:
    return _event_adapter.validate_python(fields)
