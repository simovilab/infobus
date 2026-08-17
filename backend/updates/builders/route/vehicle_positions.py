import logging
from typing import cast

from django.conf import settings
from django.utils import timezone
from redis import Redis
from runs.models import Run
from runs.services.lifecycle import ACTIVE_STATES, active_runs_key

from updates.schemas import VehiclePositionSnapshot, VehiclePositionsByRouteSnapshot
from updates.topics import TopicKey


logger: logging.Logger = logging.getLogger(__name__)
r: Redis = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_CELERY_DB,
    decode_responses=True,
)

SCALAR_FIELDS: tuple[str, ...] = (
    "current_stop_sequence",
    "stop_id",
    "current_status",
    "congestion_level",
    "occupancy_status",
    "occupancy_percentage",
    "timestamp",
)


def _optional_float(value: object, *, key: str, run_id: str) -> float | None:
    """Parse an optional float and warn when a present value is malformed."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        logger.warning("Unable to parse Redis key %s for run %s as float", key, run_id)
        return None


def _optional_int(value: object, *, key: str, run_id: str) -> int | None:
    """Parse an optional integer and warn when a present value is malformed."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        logger.warning(
            "Unable to parse Redis key %s for run %s as integer", key, run_id
        )
        return None


def _position_field_key(position_key: str, field: str) -> str:
    """Identify one field within a Redis position hash for logging."""
    return f"{position_key}[{field}]"


def _scalar_keys(transit_system: str, run_id: str) -> list[str]:
    """Return the ordered Redis scalar keys for one run."""
    return [f"{transit_system}:trip:{run_id}:{field}" for field in SCALAR_FIELDS]


def _run_id_sort_key(vehicle: VehiclePositionSnapshot) -> str:
    """Return the textual run identifier used by the public ordering contract."""
    return str(vehicle.run_id)


def build_route_vehicle_positions(topic: TopicKey) -> dict[str, object]:
    """Build the current vehicle-position snapshot for one route."""
    route_id: str = topic.primary_value
    runs: list[Run] = list(
        Run.objects.filter(
            route_id=route_id,
            feed_publisher__transit_system__code=topic.transit_system,
            run_lifecycle_state__in=ACTIVE_STATES,
        )
        .only("id", "trip_id", "route_id", "direction_id")
        .order_by("id")
    )
    if not runs:
        return VehiclePositionsByRouteSnapshot(
            topic=topic.render(),
            route_id=route_id,
            vehicles=[],
        ).model_dump(mode="json")

    run_ids: list[str] = [str(run.id) for run in runs]
    with r.pipeline(transaction=False) as pipe:
        pipe.smismember(active_runs_key(topic.transit_system), run_ids)
        for run_id in run_ids:
            pipe.hgetall(f"{topic.transit_system}:trip:{run_id}:position")
        for run_id in run_ids:
            pipe.mget(_scalar_keys(topic.transit_system, run_id))
        values: list[object] = pipe.execute()

    memberships: list[int] = cast(list[int], values[0])
    positions: list[dict[str, str]] = cast(
        list[dict[str, str]], values[1 : 1 + len(run_ids)]
    )
    scalar_values: list[list[str | None]] = cast(
        list[list[str | None]], values[1 + len(run_ids) :]
    )
    stale_before: int = int(timezone.now().timestamp()) - int(
        settings.GTFS_RT_VEHICLE_POSITION_STALE_TOLERANCE_SECONDS
    )

    vehicles: list[VehiclePositionSnapshot] = []
    for run, run_id, is_active, position, raw_scalars in zip(
        runs,
        run_ids,
        memberships,
        positions,
        scalar_values,
        strict=True,
    ):
        if not is_active:
            continue

        position_key: str = f"{topic.transit_system}:trip:{run_id}:position"
        latitude: float | None = _optional_float(
            position.get("latitude"),
            key=_position_field_key(position_key, "latitude"),
            run_id=run_id,
        )
        longitude: float | None = _optional_float(
            position.get("longitude"),
            key=_position_field_key(position_key, "longitude"),
            run_id=run_id,
        )
        if latitude is None or longitude is None:
            continue

        scalars: dict[str, str | None] = dict(
            zip(SCALAR_FIELDS, raw_scalars, strict=True)
        )
        scalar_keys: dict[str, str] = dict(
            zip(
                SCALAR_FIELDS,
                _scalar_keys(topic.transit_system, run_id),
                strict=True,
            )
        )
        timestamp: int | None = _optional_int(
            scalars["timestamp"],
            key=scalar_keys["timestamp"],
            run_id=run_id,
        )
        if timestamp is not None and timestamp < stale_before:
            continue

        vehicles.append(
            VehiclePositionSnapshot(
                run_id=run.id,
                trip_id=run.trip_id,
                route_id=run.route_id,
                direction_id=run.direction_id,
                latitude=latitude,
                longitude=longitude,
                bearing=_optional_float(
                    position.get("bearing"),
                    key=_position_field_key(position_key, "bearing"),
                    run_id=run_id,
                ),
                speed=_optional_float(
                    position.get("speed"),
                    key=_position_field_key(position_key, "speed"),
                    run_id=run_id,
                ),
                odometer=_optional_float(
                    position.get("odometer"),
                    key=_position_field_key(position_key, "odometer"),
                    run_id=run_id,
                ),
                current_stop_sequence=_optional_int(
                    scalars["current_stop_sequence"],
                    key=scalar_keys["current_stop_sequence"],
                    run_id=run_id,
                ),
                stop_id=scalars["stop_id"],
                current_status=_optional_int(
                    scalars["current_status"],
                    key=scalar_keys["current_status"],
                    run_id=run_id,
                ),
                congestion_level=_optional_int(
                    scalars["congestion_level"],
                    key=scalar_keys["congestion_level"],
                    run_id=run_id,
                ),
                occupancy_status=_optional_int(
                    scalars["occupancy_status"],
                    key=scalar_keys["occupancy_status"],
                    run_id=run_id,
                ),
                occupancy_percentage=_optional_int(
                    scalars["occupancy_percentage"],
                    key=scalar_keys["occupancy_percentage"],
                    run_id=run_id,
                ),
                timestamp=timestamp,
            )
        )

    vehicles.sort(key=_run_id_sort_key)
    return VehiclePositionsByRouteSnapshot(
        topic=topic.render(),
        route_id=route_id,
        vehicles=vehicles,
    ).model_dump(mode="json")
