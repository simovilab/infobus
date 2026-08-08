import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from feed.models import Feed, FeedPublisher, StopTime, TransitSystem
from redis import Redis

from runs.domain.lifecycle import RunLifecycleStates
from runs.events.types import (
    RunCancelled,
    RunCompleted,
    RunInterrupted,
    RunLifecycleEvent,
    RunSignalLost,
    RunSignalRestored,
)
from runs.models import Run


RealtimeSource = Literal["vehicle_positions", "trip_updates"]

ACTIVE_STATES = {
    RunLifecycleStates.IN_PROGRESS.value,
    RunLifecycleStates.NO_SIGNAL.value,
}
TERMINAL_STATES = {
    RunLifecycleStates.CANCELLED.value,
    RunLifecycleStates.COMPLETED.value,
    RunLifecycleStates.INTERRUPTED.value,
    RunLifecycleStates.SHORT_TURNED.value,
}

r = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_CELERY_DB,
    decode_responses=True,
)


@dataclass(frozen=True)
class LifecycleEvidence:
    """Collect the evidence used to classify an unseen active run."""

    last_seen_at: datetime
    feed_healthy: bool
    at_terminal_stop: bool = False
    near_terminal_stop: bool = False
    expected_end_at: datetime | None = None


@dataclass(frozen=True)
class LifecycleDecision:
    """Describe a lifecycle state transition and its reason."""

    state: str
    reason: str


def active_runs_key(transit_system: str) -> str:
    """Return the canonical Redis set for active runs in a transit system."""
    return f"{transit_system}:runs:active"


def last_seen_key(transit_system: str) -> str:
    """Return the Redis sorted set storing run observation timestamps."""
    return f"{transit_system}:runs:last_seen"


def feed_success_key(feed_publisher: FeedPublisher, source: RealtimeSource) -> str:
    """Return the Redis key storing one realtime source's last success."""
    return (
        f"{feed_publisher.transit_system.code}:publisher:{feed_publisher.pk}:"
        f"{source}:last_success"
    )


def decide_run_lifecycle(
    current_state: str,
    evidence: LifecycleEvidence,
    now: datetime,
) -> LifecycleDecision | None:
    """Classify an unseen run using feed health, progress, and schedule time."""
    if current_state in TERMINAL_STATES or not evidence.feed_healthy:
        return None

    unseen_for = max(now - evidence.last_seen_at, timedelta())
    no_signal_after = timedelta(seconds=settings.RUN_NO_SIGNAL_AFTER_SECONDS)
    if unseen_for < no_signal_after:
        return None

    terminal_grace = timedelta(seconds=settings.RUN_TERMINAL_SILENCE_GRACE_SECONDS)
    if evidence.at_terminal_stop and unseen_for >= terminal_grace:
        return LifecycleDecision(
            RunLifecycleStates.COMPLETED.value,
            "Stopped at the terminal stop before realtime updates ceased.",
        )

    expected_end_grace = timedelta(seconds=settings.RUN_EXPECTED_END_GRACE_SECONDS)
    if (
        evidence.expected_end_at is not None
        and now >= evidence.expected_end_at + expected_end_grace
    ):
        if evidence.near_terminal_stop:
            return LifecycleDecision(
                RunLifecycleStates.COMPLETED.value,
                "Realtime updates ceased near the terminal after the expected end.",
            )
        return LifecycleDecision(
            RunLifecycleStates.INTERRUPTED.value,
            "Realtime updates ceased before terminal progress after the expected end.",
        )

    unknown_timeout = timedelta(seconds=settings.RUN_UNKNOWN_TIMEOUT_SECONDS)
    if evidence.expected_end_at is None and unseen_for >= unknown_timeout:
        return LifecycleDecision(
            RunLifecycleStates.INTERRUPTED.value,
            "Realtime updates ceased and no expected end time was available.",
        )

    if current_state != RunLifecycleStates.NO_SIGNAL.value:
        return LifecycleDecision(
            RunLifecycleStates.NO_SIGNAL.value,
            "Run is absent from healthy realtime feeds beyond the signal grace period.",
        )
    return None


def record_successful_poll(
    feed_publisher: FeedPublisher,
    source: RealtimeSource,
    run_ids: Iterable[UUID | str],
    observed_at: datetime | None = None,
) -> None:
    """Record feed health and refresh all runs observed in one successful poll."""
    observed_at = observed_at or timezone.now()
    run_id_strings = {str(run_id) for run_id in run_ids}
    runs = list(
        Run.objects.filter(id__in=run_id_strings).select_related(
            "feed_publisher__transit_system"
        )
    )
    active_runs = [
        run
        for run in runs
        if run.run_lifecycle_state not in TERMINAL_STATES
        and run.schedule_relationship not in {"CANCELED", "DELETED"}
    ]
    transit_system = feed_publisher.transit_system.code

    with r.pipeline(transaction=True) as pipe:
        pipe.set(feed_success_key(feed_publisher, source), observed_at.timestamp())
        if active_runs:
            mapping = {str(run.id): observed_at.timestamp() for run in active_runs}
            pipe.zadd(last_seen_key(transit_system), mapping)
            pipe.sadd(active_runs_key(transit_system), *mapping)
        pipe.execute()

    if active_runs:
        Run.objects.filter(id__in=[run.id for run in active_runs]).update(
            last_seen_at=observed_at,
            missing_since=None,
        )

    for run in active_runs:
        if run.run_lifecycle_state == RunLifecycleStates.NO_SIGNAL.value:
            transition_run(
                run.id,
                RunLifecycleStates.IN_PROGRESS.value,
                "Run reappeared in a successful realtime poll.",
                occurred_at=observed_at,
                last_seen_at=observed_at,
            )

    for run in runs:
        if (
            run.run_lifecycle_state not in TERMINAL_STATES
            and run.schedule_relationship in {"CANCELED", "DELETED"}
        ):
            transition_run(
                run.id,
                RunLifecycleStates.CANCELLED.value,
                f"GTFS Realtime marked the run {run.schedule_relationship}.",
                occurred_at=observed_at,
                last_seen_at=observed_at,
            )


def publisher_realtime_healthy(
    feed_publisher: FeedPublisher,
    now: datetime,
) -> bool:
    """Return whether every configured run-bearing realtime source is fresh."""
    sources: list[RealtimeSource] = []
    if feed_publisher.vehicle_positions_url:
        sources.append("vehicle_positions")
    if feed_publisher.trip_updates_url:
        sources.append("trip_updates")
    if not sources:
        return False

    max_age = settings.RUN_FEED_HEALTH_MAX_AGE_SECONDS
    for source in sources:
        value = r.get(feed_success_key(feed_publisher, source))
        if value is None or now.timestamp() - float(value) > max_age:
            return False
    return True


def evaluate_active_runs(now: datetime | None = None) -> dict[str, int]:
    """Evaluate all canonical active sets and apply justified transitions."""
    now = now or timezone.now()
    counts: dict[str, int] = {}

    for transit_system in TransitSystem.objects.all():
        system_code = transit_system.code
        run_ids = list(r.smembers(active_runs_key(system_code)))
        if not run_ids:
            continue

        runs = list(
            Run.objects.filter(id__in=run_ids).select_related(
                "feed_publisher__transit_system"
            )
        )
        last_seen_scores = r.zmscore(last_seen_key(system_code), run_ids)
        last_seen_by_id = dict(zip(run_ids, last_seen_scores))
        health_by_publisher: dict[int, bool] = {}

        for run in runs:
            if run.run_lifecycle_state in TERMINAL_STATES:
                _apply_redis_transition(run, publish_event=False)
                continue

            publisher_id = run.feed_publisher_id
            if publisher_id not in health_by_publisher:
                health_by_publisher[publisher_id] = publisher_realtime_healthy(
                    run.feed_publisher,
                    now,
                )

            score = last_seen_by_id.get(str(run.id))
            last_seen_at = (
                datetime.fromtimestamp(float(score), tz=UTC)
                if score is not None
                else run.last_seen_at
            )
            if last_seen_at is None:
                continue

            timing = _timing_evidence(run)
            decision = decide_run_lifecycle(
                run.run_lifecycle_state,
                LifecycleEvidence(
                    last_seen_at=last_seen_at,
                    feed_healthy=health_by_publisher[publisher_id],
                    at_terminal_stop=timing.at_terminal_stop,
                    near_terminal_stop=timing.near_terminal_stop,
                    expected_end_at=timing.expected_end_at,
                ),
                now,
            )
            if decision is None:
                continue

            if transition_run(
                run.id,
                decision.state,
                decision.reason,
                occurred_at=now,
                last_seen_at=last_seen_at,
            ):
                counts[decision.state] = counts.get(decision.state, 0) + 1

    return counts


@dataclass(frozen=True)
class _TimingEvidence:
    """Bundle terminal sequence, expected end time, and proximity flags for lifecycle evaluation."""

    terminal_sequence: int | None
    expected_end_at: datetime | None
    at_terminal_stop: bool
    near_terminal_stop: bool


def _timing_evidence(run: Run) -> _TimingEvidence:
    """Resolve terminal sequence and expected end from schedule and realtime."""
    terminal_sequence, expected_end_at = _scheduled_terminal_evidence(run)
    realtime_sequence, realtime_end_at = _realtime_terminal_evidence(run)
    if terminal_sequence is None:
        terminal_sequence = realtime_sequence
    elif realtime_sequence is not None:
        terminal_sequence = max(terminal_sequence, realtime_sequence)
    if realtime_end_at is not None:
        expected_end_at = realtime_end_at

    system_code = run.feed_publisher.transit_system.code
    current_sequence_value = r.get(f"{system_code}:trip:{run.id}:current_stop_sequence")
    current_status_value = r.get(f"{system_code}:trip:{run.id}:current_status")
    current_sequence = (
        int(current_sequence_value) if current_sequence_value is not None else None
    )
    current_status = (
        int(current_status_value) if current_status_value is not None else None
    )
    near_terminal = (
        terminal_sequence is not None
        and current_sequence is not None
        and current_sequence >= max(terminal_sequence - 1, 0)
    )
    at_terminal = (
        terminal_sequence is not None
        and current_sequence is not None
        and current_sequence >= terminal_sequence
        and current_status == 1
    )
    return _TimingEvidence(
        terminal_sequence=terminal_sequence,
        expected_end_at=expected_end_at,
        at_terminal_stop=at_terminal,
        near_terminal_stop=near_terminal,
    )


def _scheduled_terminal_evidence(run: Run) -> tuple[int | None, datetime | None]:
    """Return terminal evidence from the current GTFS Schedule feed."""
    if not run.trip_id or run.start_date is None:
        return None, None
    current_feed = (
        Feed.objects.filter(feed_publisher=run.feed_publisher, is_current=True)
        .order_by("-retrieved_at")
        .first()
    )
    if current_feed is None:
        return None, None
    last_stop = (
        StopTime.objects.filter(feed=current_feed, trip_id=run.trip_id)
        .order_by("-stop_sequence")
        .values("stop_sequence", "arrival_time", "departure_time")
        .first()
    )
    if last_stop is None:
        return None, None

    end_offset = last_stop["departure_time"] or last_stop["arrival_time"]
    expected_end_at = None
    if end_offset is not None:
        try:
            publisher_timezone = ZoneInfo(run.feed_publisher.timezone)
        except ZoneInfoNotFoundError:
            publisher_timezone = ZoneInfo(settings.TIME_ZONE)
        expected_end_at = (
            datetime.combine(
                run.start_date,
                time.min,
                tzinfo=publisher_timezone,
            )
            + end_offset
        )
    return int(last_stop["stop_sequence"]), expected_end_at


def _realtime_terminal_evidence(run: Run) -> tuple[int | None, datetime | None]:
    """Return terminal evidence from the latest RedisJSON stop predictions."""
    system_code = run.feed_publisher.transit_system.code
    value = r.json().get(f"{system_code}:trip:{run.id}:stop_time_updates")
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, list):
        return None, None

    sequences: list[int] = []
    timestamps: list[int] = []
    for update in value:
        if not isinstance(update, dict):
            continue
        sequence = update.get("stop_sequence")
        if sequence is not None:
            sequences.append(int(sequence))
        for event_name in ("arrival", "departure"):
            event = update.get(event_name)
            if isinstance(event, dict) and event.get("time") is not None:
                timestamps.append(int(event["time"]))

    terminal_sequence = max(sequences) if sequences else None
    expected_end_at = (
        datetime.fromtimestamp(max(timestamps), tz=UTC) if timestamps else None
    )
    return terminal_sequence, expected_end_at


def transition_run(
    run_id: UUID | str,
    new_state: str,
    reason: str,
    *,
    occurred_at: datetime | None = None,
    last_seen_at: datetime | None = None,
) -> bool:
    """Persist one lifecycle transition and synchronize Redis after commit."""
    occurred_at = occurred_at or timezone.now()
    with r.lock(f"run:{run_id}:lifecycle_lock", timeout=15, blocking_timeout=5):
        with transaction.atomic():
            run = (
                Run.objects.select_for_update()
                .select_related("feed_publisher__transit_system")
                .get(id=run_id)
            )
            previous_state = run.run_lifecycle_state
            if previous_state == new_state:
                if new_state in TERMINAL_STATES:
                    transaction.on_commit(
                        lambda: _apply_redis_transition(run, publish_event=False)
                    )
                return False
            if previous_state in TERMINAL_STATES:
                return False

            run.run_lifecycle_state = new_state
            run.last_event_at = occurred_at
            if last_seen_at is not None:
                run.last_seen_at = last_seen_at
            if new_state == RunLifecycleStates.NO_SIGNAL.value:
                run.missing_since = last_seen_at or occurred_at
            elif new_state == RunLifecycleStates.IN_PROGRESS.value:
                run.missing_since = None
                run.ended_at = None
                run.completion_reason = None
            elif new_state in TERMINAL_STATES:
                run.ended_at = occurred_at
                run.completion_reason = reason

            run.save(
                update_fields=[
                    "run_lifecycle_state",
                    "last_event_at",
                    "last_seen_at",
                    "missing_since",
                    "ended_at",
                    "completion_reason",
                ]
            )
            transaction.on_commit(
                lambda: _apply_redis_transition(
                    run,
                    reason=reason,
                    previous_state=previous_state,
                    publish_event=True,
                )
            )
    return True


def _apply_redis_transition(
    run: Run,
    *,
    reason: str | None = None,
    previous_state: str | None = None,
    publish_event: bool,
) -> None:
    """Synchronize active membership, stop indexes, state TTLs, and events."""
    system_code = run.feed_publisher.transit_system.code
    run_id = str(run.id)
    state = run.run_lifecycle_state
    terminal = state in TERMINAL_STATES
    remaining_stops_key = f"{system_code}:run:{run_id}:remaining_stops"
    stop_ids = r.zrange(remaining_stops_key, 0, -1)
    state_keys = []
    if terminal:
        state_keys.extend(r.scan_iter(match=f"{system_code}:trip:{run_id}:*"))
        state_keys.extend(r.scan_iter(match=f"{system_code}:run:{run_id}:*"))

    with r.pipeline(transaction=True) as pipe:
        pipe.set(f"{system_code}:run:{run_id}:lifecycle_state", state)
        if terminal:
            pipe.srem(active_runs_key(system_code), run_id)
            pipe.srem("trip:in_progress", run_id)
            pipe.zrem(last_seen_key(system_code), run_id)
            pipe.delete(remaining_stops_key)
            pipe.delete(f"{system_code}:run:{run_id}:remaining_stops_initialized")
            for stop_id in stop_ids:
                pipe.srem(
                    f"{system_code}:stop:{stop_id}:approaching_runs",
                    run_id,
                )
            for key in state_keys:
                pipe.expire(key, settings.RUN_TERMINAL_STATE_TTL_SECONDS)
        else:
            pipe.sadd(active_runs_key(system_code), run_id)

        if publish_event:
            event = _lifecycle_event(
                run,
                reason=reason or "Run lifecycle state changed.",
                previous_state=previous_state,
                affected_stop_ids=stop_ids,
            )
            pipe.xadd("events", event.redis_fields())
        pipe.execute()


def _lifecycle_event(
    run: Run,
    *,
    reason: str,
    previous_state: str | None,
    affected_stop_ids: list[str],
) -> RunLifecycleEvent:
    """Build the typed domain event for a persisted lifecycle state."""
    event_types: dict[str, type[RunLifecycleEvent]] = {
        RunLifecycleStates.NO_SIGNAL.value: RunSignalLost,
        RunLifecycleStates.IN_PROGRESS.value: RunSignalRestored,
        RunLifecycleStates.COMPLETED.value: RunCompleted,
        RunLifecycleStates.INTERRUPTED.value: RunInterrupted,
        RunLifecycleStates.CANCELLED.value: RunCancelled,
    }
    event_type = event_types[run.run_lifecycle_state]
    contextual_reason = (
        f"{reason} Previous state: {previous_state}."
        if previous_state is not None
        else reason
    )
    return event_type(
        transit_system=run.feed_publisher.transit_system.code,
        run_id=run.id,
        reason=contextual_reason,
        occurred_at=run.last_event_at or timezone.now(),
        last_seen_at=run.last_seen_at,
        affected_stop_ids_json=json.dumps(affected_stop_ids),
    )
