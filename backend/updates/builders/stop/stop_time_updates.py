import json
import logging
from typing import Any, cast

from django.conf import settings
from django.utils import timezone
from pydantic import ValidationError
from redis import Redis
from runs.models import Run
from runs.services.lifecycle import active_runs_key
from runs.services.stop_index import approaching_run_ids, run_is_approaching_stop

from updates.projections.stop.stop_time_updates import direction_id_from_topic
from updates.schemas import (
    DirectionID,
    StopTimeEventSnapshot,
    StopTimeUpdateSnapshot,
    StopTimeUpdatesByStopSnapshot,
)
from updates.topics import TopicKey


logger = logging.getLogger(__name__)
r = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_CELERY_DB,
    decode_responses=True,
)

SCHEDULE_RELATIONSHIPS = {
    0: "SCHEDULED",
    1: "SKIPPED",
    2: "NO_DATA",
    3: "UNSCHEDULED",
}


def _decode_stop_time_updates(value: object) -> list[dict[str, Any]]:
    """Decode current RedisJSON and the legacy JSON-string representation."""
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _schedule_relationship_name(value: object) -> Any:
    """Normalize known GTFS enum encodings while leaving corruption invalid."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return SCHEDULE_RELATIONSHIPS.get(value, value)
    if isinstance(value, str):
        normalized = value.upper()
        if normalized in SCHEDULE_RELATIONSHIPS.values():
            return normalized
        if normalized.isdigit():
            return SCHEDULE_RELATIONSHIPS.get(int(normalized), value)
    return value


def _event_snapshot(value: object) -> StopTimeEventSnapshot:
    event = value if isinstance(value, dict) else {}
    return StopTimeEventSnapshot(
        delay=event.get("delay"),
        time=event.get("time"),
        uncertainty=event.get("uncertainty"),
    )


def _current_documents(
    transit_system: str,
    run_ids: list[str],
) -> tuple[list[object], list[int | None]]:
    """Bulk-read prediction documents and current sequences for selected runs."""
    if not run_ids:
        return [], []

    with r.pipeline(transaction=False) as pipe:
        for run_id in run_ids:
            pipe.json().get(f"{transit_system}:trip:{run_id}:stop_time_updates")
        for run_id in run_ids:
            pipe.get(f"{transit_system}:trip:{run_id}:current_stop_sequence")
        values = pipe.execute()

    document_values = values[: len(run_ids)]
    sequence_values = values[len(run_ids) :]
    current_sequences: list[int | None] = []
    for value in sequence_values:
        try:
            current_sequences.append(int(value) if value is not None else None)
        except (TypeError, ValueError):
            current_sequences.append(None)
    return document_values, current_sequences


def _predicted_time(update: StopTimeUpdateSnapshot) -> int | None:
    """Return the GTFS-RT event time relevant to this stop visit."""
    if update.arrival.time is not None:
        return update.arrival.time
    return update.departure.time


def _sort_key(update: StopTimeUpdateSnapshot) -> tuple[bool, int, str, bool, int]:
    predicted_time = _predicted_time(update)
    return (
        predicted_time is None,
        predicted_time or 0,
        str(update.run_id),
        update.stop_sequence is None,
        update.stop_sequence or 0,
    )


def build_stop_time_updates(topic: TopicKey) -> dict[str, object]:
    """Build a complete current stop/direction snapshot from active Redis state.

    Lifecycle and stop indexes remain authoritative. A small temporal tolerance
    at this public boundary also prevents delayed cleanup from exposing
    predictions that are hours or days old. Timestamp-free updates remain valid
    because their indexed run/progress evidence can still be current.
    """
    stop_id = topic.primary_value
    direction_id = direction_id_from_topic(topic)
    earliest_relevant_time = int(timezone.now().timestamp()) - int(
        settings.GTFS_RT_STOP_TIME_UPDATE_PAST_TOLERANCE_SECONDS
    )
    active_run_ids = {
        str(run_id) for run_id in r.smembers(active_runs_key(topic.transit_system))
    }
    candidate_run_ids = [
        run_id
        for run_id in approaching_run_ids(topic.transit_system, stop_id)
        if run_id in active_run_ids
        if run_is_approaching_stop(topic.transit_system, run_id, stop_id)
    ]
    runs_by_id = {
        str(run.id): run
        for run in Run.objects.filter(
            id__in=candidate_run_ids,
            feed_publisher__transit_system__code=topic.transit_system,
        ).select_related("feed_publisher__transit_system")
    }
    selected_run_ids = [
        run_id
        for run_id in candidate_run_ids
        if (run := runs_by_id.get(run_id)) is not None
        if run.feed_publisher.transit_system.code == topic.transit_system
        if run.direction_id == direction_id
    ]

    documents, current_sequences = _current_documents(
        topic.transit_system,
        selected_run_ids,
    )
    updates: list[StopTimeUpdateSnapshot] = []
    for run_id, document, current_sequence in zip(
        selected_run_ids,
        documents,
        current_sequences,
    ):
        run = runs_by_id[run_id]
        for raw_update in _decode_stop_time_updates(document):
            if str(raw_update.get("stop_id")) != stop_id:
                continue

            raw_sequence = raw_update.get("stop_sequence")
            try:
                stop_sequence = int(raw_sequence) if raw_sequence is not None else None
            except (TypeError, ValueError):
                continue
            if current_sequence is not None and (
                stop_sequence is None or stop_sequence < current_sequence
            ):
                continue

            try:
                update = StopTimeUpdateSnapshot(
                    run_id=run.id,
                    trip_id=run.trip_id,
                    route_id=run.route_id,
                    direction_id=cast(DirectionID, run.direction_id),
                    stop_id=stop_id,
                    stop_sequence=stop_sequence,
                    arrival=_event_snapshot(raw_update.get("arrival")),
                    departure=_event_snapshot(raw_update.get("departure")),
                    schedule_relationship=_schedule_relationship_name(
                        raw_update.get("schedule_relationship")
                    ),
                )
            except ValidationError:
                logger.warning(
                    "Ignoring invalid current StopTimeUpdate for run %s and stop %s",
                    run_id,
                    stop_id,
                    exc_info=True,
                )
                continue
            if update.schedule_relationship == "SKIPPED":
                continue
            predicted_time = _predicted_time(update)
            if predicted_time is not None and predicted_time < earliest_relevant_time:
                continue
            updates.append(update)

    updates.sort(key=_sort_key)
    snapshot = StopTimeUpdatesByStopSnapshot(
        topic=topic.render(),
        stop_id=stop_id,
        direction_id=direction_id,
        stop_time_updates=updates,
    )
    return snapshot.model_dump(mode="json")


# Keep the legacy import in builders.message_builder importable.
stop_time_updates = build_stop_time_updates
