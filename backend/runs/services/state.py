"""
Implementation of the events service, which is responsible for handling the following events related to runs in progress:

- CurrentStopSequenceChanged
- StopIdChanged
- CurrentStatusChanged
- CongestionLevelChanged
- OccupancyStatusChanged
- OccupancyPercentageChanged
- DelayChanged
- TripPropertiesChanged

Updates the following states:

On run registration:
- trip:<run_id>:trip
- trip:<run_id>:vehicle

By vehicle positions:
- trip:<run_id>:position (Redis: hash)
- trip:<run_id>:current_stop_sequence (Redis: string)
- trip:<run_id>:stop_id (Redis: string)
- trip:<run_id>:current_status (Redis: string)
- trip:<run_id>:timestamp (Redis: string)
- trip:<run_id>:congestion_level (Redis: string)
- trip:<run_id>:occupancy_status (Redis: string)
- trip:<run_id>:occupancy_percentage (Redis: string)
- trip:<run_id>:multi_carriage_details (Redis: JSON)

By trip updates:
- trip:<run_id>:stop_time_updates
- trip:<run_id>:delay
- trip:<run_id>:trip_properties
"""

from collections.abc import Callable
from redis import Redis
from redis.exceptions import WatchError
from typing import TypeAlias, TypeVar
from uuid import UUID
from django.conf import settings
from feed.models import FeedPublisher
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from runs.services.realtime import confirm_run
from runs.events.detector import EventDetector
from runs.services.stop_index import advance_remaining_stops, sync_remaining_stops

StateT = TypeVar("StateT", int, str)
StateDeserializer: TypeAlias = Callable[[bytes], StateT]
StateDetector: TypeAlias = Callable[
    [FeedPublisher, UUID, StateT | None, StateT],
    dict[str, object] | None,
]

r = Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_CELERY_DB
)


def _update_state_and_publish_event(
    key: str,
    current_state: StateT,
    deserialize: StateDeserializer[StateT],
    detector: StateDetector[StateT],
    feed_publisher: FeedPublisher,
    run_id: UUID,
) -> None:
    """Atomically store one Redis state value and publish an event when its detector reports a change."""
    while True:
        with r.pipeline() as pipe:
            try:
                pipe.watch(key)
                previous_value = pipe.get(key)
                previous_state = (
                    deserialize(previous_value) if previous_value is not None else None
                )
                event = detector(
                    feed_publisher,
                    run_id,
                    previous_state,
                    current_state,
                )

                pipe.multi()
                pipe.set(key, current_state)
                if event is not None:
                    pipe.xadd("events", event)
                pipe.execute()
                return
            except WatchError:
                continue


def update_vehicle_positions_state(
    feed_publisher: FeedPublisher,
    vehicle_positions: gtfs_rt.FeedMessage,
) -> set[UUID]:
    """Update vehicle state and return the runs observed in the feed."""
    observed_run_ids: set[UUID] = set()
    entities = vehicle_positions.entity
    for entity in entities:
        v = entity.vehicle
        if not v.HasField("trip"):
            continue
        run_id = confirm_run(feed_publisher, v.trip)
        observed_run_ids.add(run_id)

        # trip:<run_id>:position (Redis: hash)
        if v.HasField("position"):
            position = {
                "latitude": v.position.latitude
                if v.position.HasField("latitude")
                else None,
                "longitude": v.position.longitude
                if v.position.HasField("longitude")
                else None,
                "bearing": v.position.bearing
                if v.position.HasField("bearing")
                else None,
                "speed": v.position.speed if v.position.HasField("speed") else None,
                "odometer": v.position.odometer
                if v.position.HasField("odometer")
                else None,
            }
            position = {
                field: value for field, value in position.items() if value is not None
            }
            if position:
                r.hset(
                    f"{feed_publisher.transit_system.code}:trip:{run_id}:position",
                    mapping=position,
                )

        # trip:<run_id>:current_stop_sequence (Redis: string)
        if v.HasField("current_stop_sequence"):
            current_stop_sequence = int(v.current_stop_sequence)
            _update_state_and_publish_event(
                f"{feed_publisher.transit_system.code}:trip:{run_id}:current_stop_sequence",
                current_stop_sequence,
                int,
                EventDetector.current_stop_sequence,
                feed_publisher,
                run_id,
            )
            advance_remaining_stops(
                feed_publisher.transit_system.code,
                run_id,
                current_stop_sequence,
            )

        # trip:<run_id>:stop_id (Redis: string)
        if v.HasField("stop_id"):
            _update_state_and_publish_event(
                f"{feed_publisher.transit_system.code}:trip:{run_id}:stop_id",
                v.stop_id,
                lambda value: value.decode("utf-8"),
                EventDetector.stop_id,
                feed_publisher,
                run_id,
            )

        # trip:<run_id>:current_status (Redis: string)
        if v.HasField("current_status"):
            _update_state_and_publish_event(
                f"{feed_publisher.transit_system.code}:trip:{run_id}:current_status",
                int(v.current_status),
                int,
                EventDetector.current_status,
                feed_publisher,
                run_id,
            )

        # trip:<run_id>:timestamp (Redis: string)
        if v.HasField("timestamp"):
            r.set(
                f"{feed_publisher.transit_system.code}:trip:{run_id}:timestamp",
                v.timestamp,
            )

        # trip:<run_id>:congestion_level (Redis: string)
        if v.HasField("congestion_level"):
            _update_state_and_publish_event(
                f"{feed_publisher.transit_system.code}:trip:{run_id}:congestion_level",
                int(v.congestion_level),
                int,
                EventDetector.congestion_level,
                feed_publisher,
                run_id,
            )

        # trip:<run_id>:occupancy_status (Redis: string)
        if v.HasField("occupancy_status"):
            _update_state_and_publish_event(
                f"{feed_publisher.transit_system.code}:trip:{run_id}:occupancy_status",
                int(v.occupancy_status),
                int,
                EventDetector.occupancy_status,
                feed_publisher,
                run_id,
            )

        # trip:<run_id>:occupancy_percentage (Redis: string)
        if v.HasField("occupancy_percentage"):
            _update_state_and_publish_event(
                f"{feed_publisher.transit_system.code}:trip:{run_id}:occupancy_percentage",
                int(v.occupancy_percentage),
                int,
                EventDetector.occupancy_percentage,
                feed_publisher,
                run_id,
            )

        # trip:<run_id>:multi_carriage_details (Redis: JSON)

    return observed_run_ids


def update_trip_updates_state(
    feed_publisher: FeedPublisher,
    trip_updates: gtfs_rt.FeedMessage,
) -> set[UUID]:
    """Update trip state and return the runs observed in the feed."""
    observed_run_ids: set[UUID] = set()
    entities = trip_updates.entity
    for entity in entities:
        t = entity.trip_update
        if not t.HasField("trip"):
            continue
        run_id = confirm_run(feed_publisher, t.trip)
        observed_run_ids.add(run_id)

        # trip:<run_id>:stop_time_updates (Redis: JSON)
        stop_time_updates = []
        for stu in t.stop_time_update:
            stop_time_updates.append(
                {
                    "stop_sequence": stu.stop_sequence,
                    "stop_id": stu.stop_id,
                    "arrival": {
                        "delay": stu.arrival.delay
                        if stu.arrival.HasField("delay")
                        else None,
                        "time": stu.arrival.time
                        if stu.arrival.HasField("time")
                        else None,
                        "uncertainty": stu.arrival.uncertainty
                        if stu.arrival.HasField("uncertainty")
                        else None,
                    },
                    "departure": {
                        "delay": stu.departure.delay
                        if stu.departure.HasField("delay")
                        else None,
                        "time": stu.departure.time
                        if stu.departure.HasField("time")
                        else None,
                        "uncertainty": stu.departure.uncertainty
                        if stu.departure.HasField("uncertainty")
                        else None,
                    },
                }
            )
        sync_remaining_stops(
            feed_publisher.transit_system.code,
            run_id,
            (
                (stu.stop_id, stu.stop_sequence)
                for stu in t.stop_time_update
                if stu.HasField("stop_id") and stu.HasField("stop_sequence")
            ),
        )
        r.json().set(
            f"{feed_publisher.transit_system.code}:trip:{run_id}:stop_time_updates",
            "$",
            stop_time_updates,
        )

        # trip:<run_id>:delay (Redis: string)
        if t.HasField("delay"):
            r.set(
                f"{feed_publisher.transit_system.code}:trip:{run_id}:delay",
                t.delay,
            )
        # trip:<run_id>:trip_properties (Redis: JSON)

    return observed_run_ids
