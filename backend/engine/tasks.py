from celery import shared_task, group
import logging
from typing import TypedDict

import requests
from django.conf import settings
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from feed.models import TransitSystem, FeedPublisher
from feed.services.schedule import save_schedule_to_database
from feed.services.realtime import (
    save_vehicle_positions_to_database,
    save_trip_updates_to_database,
    save_alerts_to_database,
)
from feed.services.data import (
    vehicle_positions_to_parquet,
    stop_time_updates_to_parquet,
)
from runs.services.state import (
    update_vehicle_positions_state,
    update_trip_updates_state,
)
from runs.services.lifecycle import (
    evaluate_active_runs,
    r as lifecycle_redis,
    record_successful_poll,
)
from updates.refresh import refresh_active_stop_time_update_topics

logging.basicConfig(
    format="%(levelname)s: %(message)s",
    encoding="utf-8",
    level=logging.INFO,
)


class ScheduleUpdateResult(TypedDict):
    has_feed_publishers: bool
    has_new_feed: dict[str, bool]


@shared_task
def get_schedule() -> ScheduleUpdateResult:
    """Check active publishers for updated GTFS Schedule feeds and report which ones changed."""
    feed_publishers = FeedPublisher.objects.filter(is_active=True)
    result: ScheduleUpdateResult = {
        "has_feed_publishers": feed_publishers.exists(),
        "has_new_feed": {},
    }

    if not result["has_feed_publishers"]:
        logging.warning(
            "No active feed publishers found in the database. Please add at least one active publisher to fetch schedules."
        )
        return result

    for feed_publisher in feed_publishers:
        save_schedule_to_database(feed_publisher, result)

    return result


@shared_task
def get_vehicle_positions() -> str:
    """Fetch and persist vehicle-position feeds for active publishers, update run state, and record observed runs."""
    transit_systems = TransitSystem.objects.filter(is_active=True)
    if not transit_systems.exists():
        logging.warning(
            "No active transit systems found in the database. "
            "Please add at least one active transit system to fetch vehicle positions."
        )
        return "No active transit systems found."
    for transit_system in transit_systems:
        feed_publishers = FeedPublisher.objects.filter(
            transit_system=transit_system, is_active=True
        )
        if not feed_publishers.exists():
            logging.warning(
                f"No active feed publishers found for transit system {transit_system.code}."
                "Please add at least one active publisher to fetch vehicle positions."
            )
            continue
        for feed_publisher in feed_publishers:
            # Fetch VehiclePosition feed from the publisher's URL
            vehicle_positions = gtfs_rt.FeedMessage()
            try:
                vehicle_positions_response = requests.get(
                    feed_publisher.vehicle_positions_url
                )
                vehicle_positions.ParseFromString(vehicle_positions_response.content)
            except requests.RequestException as e:
                logging.error(
                    f"Error fetching vehicle positions from {feed_publisher.vehicle_positions_url}: {e}"
                )
                continue

            save_vehicle_positions_to_database(feed_publisher, vehicle_positions)
            observed_run_ids = update_vehicle_positions_state(
                feed_publisher,
                vehicle_positions,
            )
            record_successful_poll(
                feed_publisher,
                "vehicle_positions",
                observed_run_ids,
            )

    return "VehiclePositions have been processed"


@shared_task
def get_trip_updates() -> str:
    """Fetch and persist trip-update feeds for active publishers, update run state, and record observed runs."""
    transit_systems = TransitSystem.objects.filter(is_active=True)
    if not transit_systems.exists():
        logging.warning(
            "No active transit systems found in the database. "
            "Please add at least one active transit system to fetch trip updates."
        )
        return "No active transit systems found."
    successfully_polled_systems: set[str] = set()
    for transit_system in transit_systems:
        feed_publishers = FeedPublisher.objects.filter(
            transit_system=transit_system, is_active=True
        )
        if not feed_publishers.exists():
            logging.warning(
                f"No active feed publishers found for transit system {transit_system.code}."
                "Please add at least one active publisher to fetch trip updates."
            )
            continue
        for feed_publisher in feed_publishers:
            trip_updates = gtfs_rt.FeedMessage()
            try:
                trip_updates_response = requests.get(
                    feed_publisher.trip_updates_url, timeout=10
                )
                trip_updates.ParseFromString(trip_updates_response.content)
            except requests.RequestException as e:
                logging.error(
                    f"Error fetching trip updates from {feed_publisher.trip_updates_url}: {str(e)}"
                )
                continue

            save_trip_updates_to_database(feed_publisher, trip_updates)
            observed_run_ids = update_trip_updates_state(
                feed_publisher,
                trip_updates,
            )
            record_successful_poll(
                feed_publisher,
                "trip_updates",
                observed_run_ids,
            )
            successfully_polled_systems.add(transit_system.code)

    for transit_system_code in sorted(successfully_polled_systems):
        try:
            refresh_active_stop_time_update_topics(transit_system_code)
        except Exception:
            logging.exception(
                "Failed to refresh active StopTimeUpdates topics for %s",
                transit_system_code,
            )

    return "TripUpdates have been processed"


@shared_task
def get_alerts() -> str:
    """Fetch and persist GTFS Realtime alert feeds for active publishers."""
    transit_systems = TransitSystem.objects.filter(is_active=True)
    if not transit_systems.exists():
        logging.warning(
            "No active transit systems found in the database. "
            "Please add at least one active transit system to fetch alerts."
        )
        return "No active transit systems found."
    for transit_system in transit_systems:
        feed_publishers = FeedPublisher.objects.filter(
            transit_system=transit_system, is_active=True
        )
        if not feed_publishers.exists():
            logging.warning(
                f"No active feed publishers found for transit system {transit_system.code}."
                "Please add at least one active publisher to fetch alerts."
            )
            continue
        for feed_publisher in feed_publishers:
            alerts = gtfs_rt.FeedMessage()
            try:
                alerts_response = requests.get(feed_publisher.alerts_url, timeout=10)
                alerts.ParseFromString(alerts_response.content)
            except requests.RequestException as e:
                logging.error(
                    f"Error fetching alerts from {feed_publisher.alerts_url}: {str(e)}"
                )
                continue

            save_alerts_to_database(feed_publisher, alerts)

    return "Alerts have been processed"


@shared_task
def update_gtfs_realtime() -> str:
    """Dispatch a Celery group that ingests vehicle positions, trip updates, and alerts from active publishers."""
    fetching = group(get_vehicle_positions.s(), get_trip_updates.s(), get_alerts.s())
    return fetching.apply_async().id


@shared_task
def evaluate_run_lifecycles() -> dict[str, int]:
    """Classify active runs using feed health, silence, and terminal evidence."""
    lock = lifecycle_redis.lock(
        "runs:lifecycle:evaluation_lock",
        timeout=settings.RUN_LIFECYCLE_EVALUATION_LOCK_SECONDS,
        blocking_timeout=0,
    )
    if not lock.acquire(blocking=False):
        logging.info("Skipping overlapping run lifecycle evaluation.")
        return {}
    try:
        return evaluate_active_runs(heartbeat=lock.reacquire)
    finally:
        lock.release()


@shared_task
def save_vehicle_positions(use_current_hour: bool | str = False) -> str:
    """Export the selected hourly vehicle-position window to GeoParquet and return a task completion message."""
    output = vehicle_positions_to_parquet(use_current_hour=use_current_hour)
    return f"Task completed: VehiclePositions exported to parquet -> {output}"


@shared_task
def save_stop_time_updates(use_current_hour: bool | str = False) -> str:
    """Export the selected hourly stop-time-update window to Parquet and return a task completion message."""
    output = stop_time_updates_to_parquet(use_current_hour=use_current_hour)
    return f"Task completed: StopTimeUpdates exported to parquet -> {output}"


@shared_task
def save_gtfs_realtime() -> str:
    """Dispatch a Celery group that exports the last complete hour of vehicle positions and stop-time updates to Hive partitions."""
    saving = group(
        save_vehicle_positions.s(),
        save_stop_time_updates.s(),
    )
    return saving.apply_async().id
