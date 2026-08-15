from collections.abc import Iterable
from uuid import UUID

from django.conf import settings
from feed.models import Feed, StopTime
from redis import Redis
from runs.models import Run
from runs.services.lifecycle import TERMINAL_STATES


r = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_CELERY_DB,
    decode_responses=True,
)


def _remaining_stops_key(transit_system: str, run_id: UUID | str) -> str:
    """Build the Redis sorted-set key used to index a run's remaining stops."""
    return f"{transit_system}:run:{run_id}:remaining_stops"


def _approaching_runs_key(transit_system: str, stop_id: str) -> str:
    """Build the Redis set key used to index runs approaching a stop."""
    return f"{transit_system}:stop:{stop_id}:approaching_runs"


def _initialized_key(transit_system: str, run_id: UUID | str) -> str:
    """Build the Redis marker key that records whether a run's stop index was initialized."""
    return f"{transit_system}:run:{run_id}:remaining_stops_initialized"


def sync_remaining_stops(
    transit_system: str,
    run_id: UUID | str,
    stops: Iterable[tuple[str, int]],
) -> None:
    """Replace a run's remaining-stop index and synchronize stop-level approaching-run sets."""
    key = _remaining_stops_key(transit_system, run_id)
    stop_sequences = {
        str(stop_id): int(stop_sequence)
        for stop_id, stop_sequence in stops
        if stop_id and stop_sequence is not None
    }
    previous_stop_ids = set(r.zrange(key, 0, -1))

    with r.pipeline(transaction=True) as pipe:
        pipe.delete(key)
        pipe.set(_initialized_key(transit_system, run_id), 1)
        if stop_sequences:
            pipe.zadd(key, stop_sequences)
        for stop_id in previous_stop_ids - stop_sequences.keys():
            pipe.srem(_approaching_runs_key(transit_system, stop_id), str(run_id))
        for stop_id in stop_sequences:
            pipe.sadd(_approaching_runs_key(transit_system, stop_id), str(run_id))
        pipe.execute()


def ensure_remaining_stops(transit_system: str, run_id: UUID | str) -> None:
    """Initialize a run's remaining-stop index from the current schedule when absent."""
    if r.exists(_initialized_key(transit_system, run_id)):
        return

    run = Run.objects.filter(
        id=run_id,
        feed_publisher__transit_system__code=transit_system,
    ).first()
    if (
        run is None
        or not run.trip_id
        or run.run_lifecycle_state in TERMINAL_STATES
        or run.schedule_relationship in {"CANCELED", "DELETED"}
    ):
        return

    current_feed = (
        Feed.objects.filter(feed_publisher=run.feed_publisher, is_current=True)
        .order_by("-retrieved_at")
        .first()
    )
    if current_feed is None:
        return

    stops = StopTime.objects.filter(
        feed=current_feed,
        trip_id=run.trip_id,
    ).values_list("stop_id", "stop_sequence")
    sync_remaining_stops(transit_system, run_id, stops)


def remaining_stop_ids(
    transit_system: str,
    run_id: UUID | str,
) -> list[str]:
    """Return the indexed stop IDs at or after a run's current stop sequence."""
    ensure_remaining_stops(transit_system, run_id)
    key = _remaining_stops_key(transit_system, run_id)
    current_sequence = r.get(f"{transit_system}:trip:{run_id}:current_stop_sequence")
    if current_sequence is None:
        return list(r.zrange(key, 0, -1))
    return list(r.zrangebyscore(key, int(current_sequence), "+inf"))


def approaching_run_ids(transit_system: str, stop_id: str) -> list[str]:
    """Return the sorted run IDs indexed as approaching a stop."""
    return sorted(r.smembers(_approaching_runs_key(transit_system, stop_id)))


def run_is_approaching_stop(
    transit_system: str,
    run_id: UUID | str,
    stop_id: str,
) -> bool:
    """Return whether a stop remains at or ahead of a run's current sequence."""
    stop_sequence = r.zscore(
        _remaining_stops_key(transit_system, run_id),
        stop_id,
    )
    if stop_sequence is None:
        return False
    current_sequence = r.get(f"{transit_system}:trip:{run_id}:current_stop_sequence")
    return current_sequence is None or stop_sequence >= int(current_sequence)


def advance_remaining_stops(
    transit_system: str,
    run_id: UUID | str,
    current_stop_sequence: int,
) -> None:
    """Remove stops before the reported sequence from the run and stop-level indexes."""
    key = _remaining_stops_key(transit_system, run_id)
    previous_sequence = f"({current_stop_sequence}"
    passed_stop_ids = r.zrangebyscore(key, "-inf", previous_sequence)
    if not passed_stop_ids:
        return

    with r.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, "-inf", previous_sequence)
        for stop_id in passed_stop_ids:
            pipe.srem(_approaching_runs_key(transit_system, stop_id), str(run_id))
        pipe.execute()


def clear_remaining_stops(transit_system: str, run_id: UUID | str) -> None:
    """Delete a run's stop index, initialization marker, and stop-level memberships."""
    key = _remaining_stops_key(transit_system, run_id)
    stop_ids = r.zrange(key, 0, -1)
    with r.pipeline(transaction=True) as pipe:
        pipe.delete(key)
        pipe.delete(_initialized_key(transit_system, run_id))
        for stop_id in stop_ids:
            pipe.srem(_approaching_runs_key(transit_system, stop_id), str(run_id))
        pipe.execute()
