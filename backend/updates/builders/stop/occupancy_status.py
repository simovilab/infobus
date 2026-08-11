import json

from django.conf import settings
from redis import Redis
from runs.models import Run
from runs.services.lifecycle import active_runs_key
from runs.services.stop_index import approaching_run_ids, run_is_approaching_stop

from updates.topics import TopicKey


r = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_CELERY_DB,
    decode_responses=True,
)


def _arrival_time(
    transit_system: str,
    run_id: str,
    stop_id: str,
) -> int | None:
    """Retrieve the predicted arrival time for a stop from a run's RedisJSON stop-time updates."""
    value = r.json().get(
        f"{transit_system}:trip:{run_id}:stop_time_updates",
        "$",
    )
    if not value:
        return None

    stop_time_updates = value[0]
    if isinstance(stop_time_updates, str):
        stop_time_updates = json.loads(stop_time_updates)

    for update in stop_time_updates:
        if str(update.get("stop_id")) == stop_id:
            return update.get("arrival", {}).get("time")
    return None


def build_stop_occupancy_status(topic: TopicKey) -> dict:
    """Assemble a stop-topic payload from active approaching runs, Redis occupancy states, and predicted arrival times."""
    stop_id = topic.primary_value
    run_ids = [
        run_id
        for run_id in approaching_run_ids(topic.transit_system, stop_id)
        if r.sismember(active_runs_key(topic.transit_system), run_id)
        if run_is_approaching_stop(topic.transit_system, run_id, stop_id)
    ]
    runs_by_id = {
        str(run.id): run
        for run in Run.objects.filter(
            id__in=run_ids,
            feed_publisher__transit_system__code=topic.transit_system,
        )
    }

    runs = []
    for run_id in run_ids:
        run = runs_by_id.get(run_id)
        occupancy_status = r.get(
            f"{topic.transit_system}:trip:{run_id}:occupancy_status"
        )
        if run is None or occupancy_status is None:
            continue
        runs.append(
            {
                "run_id": run_id,
                "trip_id": run.trip_id,
                "route_id": run.route_id,
                "arrival_time": _arrival_time(topic.transit_system, run_id, stop_id),
                "occupancy_status": int(occupancy_status),
                "lifecycle_state": run.run_lifecycle_state,
            }
        )

    runs.sort(
        key=lambda run: (
            run["arrival_time"] is None,
            run["arrival_time"] or 0,
            run["run_id"],
        )
    )
    return {
        "topic": topic.render(),
        "stop_id": stop_id,
        "runs": runs,
    }
