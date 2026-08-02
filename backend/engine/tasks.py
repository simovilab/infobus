from celery import shared_task, group
import logging
import requests
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

logging.basicConfig(
    format="%(levelname)s: %(message)s",
    encoding="utf-8",
    level=logging.INFO,
)


@shared_task
def get_schedule():
    feed_publishers = FeedPublisher.objects.filter(is_active=True)
    result = {"has_feed_publishers": feed_publishers.exists(), "has_new_feed": {}}

    if not result["has_feed_publishers"]:
        logging.warning(
            "No active feed publishers found in the database. Please add at least one active publisher to fetch schedules."
        )
        return result

    for feed_publisher in feed_publishers:
        save_schedule_to_database(feed_publisher, result)

    return result


@shared_task
def get_vehicle_positions():
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
            update_vehicle_positions_state(feed_publisher, vehicle_positions)

    return "VehiclePositions have been processed"


@shared_task
def get_trip_updates():
    transit_systems = TransitSystem.objects.filter(is_active=True)
    if not transit_systems.exists():
        logging.warning(
            "No active transit systems found in the database. "
            "Please add at least one active transit system to fetch trip updates."
        )
        return "No active transit systems found."
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
            update_trip_updates_state(feed_publisher, trip_updates)

    return "TripUpdates have been processed"


@shared_task
def get_alerts():
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
def update_gtfs_realtime():
    """Fetches GTFS Realtime feeds (VehiclePositions, TripUpdates, and Alerts)
    every few seconds from all active feed publishers, and then updates the connected services
    consuming next trips and next stops for a current trip (run).
    """
    fetching = group(get_vehicle_positions.s(), get_trip_updates.s(), get_alerts.s())
    return fetching.apply_async().id


@shared_task
def save_vehicle_positions(use_current_hour=False):
    output = vehicle_positions_to_parquet(use_current_hour=use_current_hour)
    return f"Task completed: VehiclePositions exported to parquet -> {output}"


@shared_task
def save_stop_time_updates(use_current_hour=False):
    output = stop_time_updates_to_parquet(use_current_hour=use_current_hour)
    return f"Task completed: StopTimeUpdates exported to parquet -> {output}"


@shared_task
def save_gtfs_realtime():
    """Saves GTFS Realtime VehiclePosition and StopTimeUpdate records every hour into Hive partitions
    for historical analysis. By default it exports the last complete hour. Set `use_current_hour=True`
    to export records from the current hour (debug mode).
    """
    saving = group(
        save_vehicle_positions.s(),
        save_stop_time_updates.s(),
    )
    return saving.apply_async().id
