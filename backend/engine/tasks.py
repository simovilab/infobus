from celery import shared_task

import logging
from datetime import datetime, timedelta
import pytz
from django.db import transaction
import zipfile
import io
import pandas as pd
import requests
from google.transit import gtfs_realtime_pb2 as gtfs_rt
from feed.models import (
    FeedPublisher,
    Feed,
    FeedMessage,
    VehiclePosition,
    TripUpdate,
    StopTimeUpdate,
    Agency,
    Stop,
    Shape,
    Calendar,
    CalendarDate,
    Route,
    Trip,
    StopTime,
    FeedInfo,
)

logging.basicConfig(
    format="%(levelname)s: %(message)s",
    encoding="utf-8",
    level=logging.INFO,
)


def gtfs_time(value):
    """Convert GTFS HH:MM:SS strings (including >24h) to timedelta."""
    if not value:
        return None
    if isinstance(value, timedelta):
        return value

    try:
        hours, minutes, seconds = map(int, str(value).split(":"))
    except (ValueError, AttributeError):
        return None

    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def gtfs_date(value):
    """Convert GTFS YYYYMMDD strings to date objects for Django DateField."""
    if not value:
        return None
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value

    try:
        return datetime.strptime(str(value), "%Y%m%d").date()
    except (ValueError, TypeError):
        return None


def gtfs_timestamp(value, timezone=pytz.UTC):
    """Convert GTFS unix timestamp values to timezone-aware datetime."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value

    try:
        return datetime.fromtimestamp(int(value), tz=timezone)
    except (ValueError, TypeError, OverflowError):
        return None


def normalize_gtfs_value(value):
    """Convert null-like CSV values to None before model instantiation."""
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.lower() in {"", "nan", "none", "null"}:
            return None
        return cleaned
    return value


@shared_task
def hello_world():
    return "Hello, World!"


@shared_task
def get_schedule():
    feed_publishers = FeedPublisher.objects.filter(is_active=True)
    if not feed_publishers.exists():
        logging.warning(
            "No active feed publishers found in the database. Please add at least one active publisher to fetch schedules."
        )
        return "No active feed publishers found. Schedule update skipped."

    for feed_publisher in feed_publishers:
        logging.info(
            f"Active feed publisher found: {feed_publisher.name} ({feed_publisher.code}). Proceeding with schedule update."
        )
        schedule_url = feed_publisher.schedule_url

        logging.info(
            f"\n------------\nGTFS Schedule updating session\n{feed_publisher.name}\n{datetime.now()}\nData source: {schedule_url}\n------------"
        )

        # Check if the remote feed has been updated
        current_feed = (
            Feed.objects.filter(feed_publisher=feed_publisher, is_current=True)
            .order_by("-retrieved_at")
            .first()
        )
        current_feed_tag = None
        if current_feed:
            current_feed_tag = current_feed.http_etag
        else:
            logging.info(
                "No feed records found in the table 'feeds'. New acquisition needed."
            )

        # Get the feed's ETag to compare with the last one
        feed_check = requests.head(schedule_url)
        feed_tag = feed_check.headers["ETag"]

        if not feed_tag == current_feed_tag:
            logging.info(f"Importing new detected GTFS Schedule feed: {feed_tag}")

            # Request feed
            schedule_response = requests.get(schedule_url)
            schedule_zip = zipfile.ZipFile(io.BytesIO(schedule_response.content))

            last_modified = feed_check.headers["Last-Modified"]
            last_modified = datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
            last_modified = last_modified.replace(tzinfo=pytz.UTC)
            feed_id = f"{feed_publisher.code} ({last_modified.strftime('%Y-%m-%d %H:%M:%S %Z')})"

            # Save new feed record to database with the Feed model
            if current_feed:
                current_feed.is_current = False
                current_feed.save(update_fields=["is_current"])
            feed = Feed.objects.create(
                feed_id=feed_id,
                http_etag=feed_tag,
                http_last_modified=last_modified,
                is_current=True,
                feed_publisher=feed_publisher,
            )

            tables = {
                "agency": Agency,
                "stops": Stop,
                "shapes": Shape,
                "calendar": Calendar,
                "calendar_dates": CalendarDate,
                "routes": Route,
                "trips": Trip,
                "stop_times": StopTime,
                "feed_info": FeedInfo,
            }  # They must be loaded in this order

            # Import and save tables
            for table_name in tables.keys():
                file = f"{table_name}.txt"
                if file in schedule_zip.namelist():
                    model = tables[table_name]
                    fields = [field.name for field in model._meta.fields]
                    table = pd.read_csv(
                        schedule_zip.open(file),
                        dtype=str,
                        keep_default_na=False,
                        na_values="",
                    )
                    table = table[[col for col in fields if col in table.columns]]
                    table["feed"] = feed
                    for row in table.to_dict(orient="records"):
                        instance = model(
                            **{
                                key: normalize_gtfs_value(value)
                                for key, value in row.items()
                            }
                        )
                        instance.save()
                    logging.info(f"{file} imported successfully")

            logging.info("Schedule updated successfully")
        else:
            logging.info("No new feed detected. Schedule is up to date.")

    return "Schedule update completed. Check logs for details."


@shared_task
def get_vehicle_positions():
    publishers = FeedPublisher.objects.filter(is_active=True)
    for publisher in publishers:
        vehicle_positions = gtfs_rt.FeedMessage()
        try:
            vehicle_positions_response = requests.get(publisher.vehicle_positions_url)
            print(f"Fetching vehicle positions from {publisher.vehicle_positions_url}")
            vehicle_positions.ParseFromString(vehicle_positions_response.content)
        except requests.RequestException as e:
            print(
                f"Error fetching vehicle positions from {publisher.vehicle_positions_url}: {e}"
            )
            continue

        # Save FeedMessage object
        feed_message = FeedMessage(
            feed_message_id=f"{publisher.code}-vehicle-{vehicle_positions.header.timestamp}",
            publisher=publisher,
            entity_type="vehicle",
            timestamp=gtfs_timestamp(
                vehicle_positions.header.timestamp,
                timezone=pytz.timezone(publisher.timezone),
            ),
            incrementality=vehicle_positions.header.incrementality,
            gtfs_realtime_version=vehicle_positions.header.gtfs_realtime_version,
        )
        feed_message.save()

        # Save VehiclePosition objects
        entities = vehicle_positions.entity
        vehicle_positions_to_create = []
        for entity in entities:
            v = entity.vehicle
            vehicle_positions_to_create.append(
                VehiclePosition(
                    entity_id=entity.id,
                    feed_message=feed_message,
                    trip_trip_id=v.trip.trip_id if v.trip.HasField("trip_id") else None,
                    trip_route_id=v.trip.route_id
                    if v.trip.HasField("route_id")
                    else None,
                    trip_direction_id=v.trip.direction_id
                    if v.trip.HasField("direction_id")
                    else None,
                    trip_start_time=gtfs_time(v.trip.start_time)
                    if v.trip.HasField("start_time")
                    else None,
                    trip_start_date=gtfs_date(v.trip.start_date)
                    if v.trip.HasField("start_date")
                    else None,
                    trip_schedule_relationship=v.trip.schedule_relationship
                    if v.trip.HasField("schedule_relationship")
                    else None,
                    vehicle_id=v.vehicle.id if v.vehicle.HasField("id") else None,
                    vehicle_label=v.vehicle.label
                    if v.vehicle.HasField("label")
                    else None,
                    vehicle_license_plate=v.vehicle.license_plate
                    if v.vehicle.HasField("license_plate")
                    else None,
                    position_latitude=v.position.latitude
                    if v.position.HasField("latitude")
                    else None,
                    position_longitude=v.position.longitude
                    if v.position.HasField("longitude")
                    else None,
                    position_bearing=v.position.bearing
                    if v.position.HasField("bearing")
                    else None,
                    position_odometer=v.position.odometer
                    if v.position.HasField("odometer")
                    else None,
                    position_speed=v.position.speed
                    if v.position.HasField("speed")
                    else None,
                    current_stop_sequence=v.current_stop_sequence
                    if v.current_stop_sequence is not None
                    else None,
                    stop_id=v.stop_id if v.stop_id is not None else None,
                    current_status=v.current_status
                    if v.current_status is not None
                    else None,
                    timestamp=gtfs_timestamp(v.timestamp)
                    if v.HasField("timestamp")
                    else None,
                    congestion_level=v.congestion_level
                    if v.HasField("congestion_level")
                    else None,
                    occupancy_status=v.occupancy_status
                    if v.HasField("occupancy_status")
                    else None,
                    occupancy_percentage=v.occupancy_percentage
                    if v.HasField("occupancy_percentage")
                    else None,
                )
            )

        if vehicle_positions_to_create:
            VehiclePosition.objects.bulk_create(
                vehicle_positions_to_create,
                batch_size=2000,
            )

    return "Task completed: VehiclePositions saved to database"


@shared_task
def get_trip_updates():
    publishers = FeedPublisher.objects.filter(is_active=True)
    for publisher in publishers:
        trip_updates = gtfs_rt.FeedMessage()
        try:
            trip_updates_response = requests.get(publisher.trip_updates_url, timeout=10)
            print(f"Fetching trip updates from {publisher.trip_updates_url}")
            trip_updates.ParseFromString(trip_updates_response.content)
        except requests.RequestException as e:
            print(
                f"Error fetching trip updates from {publisher.trip_updates_url}: {str(e)}"
            )
            continue

        # Save FeedMessage object
        feed_message = FeedMessage(
            feed_message_id=f"{publisher.code}-trip_updates-{trip_updates.header.timestamp}",
            publisher=publisher,
            entity_type="trip_update",
            timestamp=gtfs_timestamp(
                trip_updates.header.timestamp,
                timezone=pytz.timezone(publisher.timezone),
            ),
            incrementality=trip_updates.header.incrementality,
            gtfs_realtime_version=trip_updates.header.gtfs_realtime_version,
        )
        feed_message.save()

        # Save TripUpdate entities and their related StopTimeUpdate objects
        entities = trip_updates.entity
        trip_updates_to_create = []
        stop_time_updates_by_trip_index = []

        for entity in entities:
            t = entity.trip_update
            trip_updates_to_create.append(
                TripUpdate(
                    entity_id=entity.id,
                    feed_message=feed_message,
                    trip_trip_id=t.trip.trip_id if t.trip.HasField("trip_id") else None,
                    trip_route_id=t.trip.route_id
                    if t.trip.HasField("route_id")
                    else None,
                    trip_direction_id=t.trip.direction_id
                    if t.trip.HasField("direction_id")
                    else None,
                    trip_start_time=gtfs_time(t.trip.start_time)
                    if t.trip.HasField("start_time")
                    else None,
                    trip_start_date=gtfs_date(t.trip.start_date)
                    if t.trip.HasField("start_date")
                    else None,
                    trip_schedule_relationship=t.trip.schedule_relationship
                    if t.trip.HasField("schedule_relationship")
                    else None,
                    vehicle_id=t.vehicle.id if t.vehicle.HasField("id") else None,
                    vehicle_label=t.vehicle.label
                    if t.vehicle.HasField("label")
                    else None,
                    vehicle_license_plate=t.vehicle.license_plate
                    if t.vehicle.HasField("license_plate")
                    else None,
                    timestamp=gtfs_timestamp(t.timestamp)
                    if t.HasField("timestamp")
                    else None,
                    delay=t.delay if t.HasField("delay") else None,
                )
            )

            stop_time_updates_by_trip_index.append(list(t.stop_time_update))

        if trip_updates_to_create:
            with transaction.atomic():
                created_trip_updates = TripUpdate.objects.bulk_create(
                    trip_updates_to_create,
                    batch_size=1000,
                )

                stop_time_updates_to_create = []
                for trip_update, stop_time_updates in zip(
                    created_trip_updates, stop_time_updates_by_trip_index
                ):
                    for stu in stop_time_updates:
                        stop_time_updates_to_create.append(
                            StopTimeUpdate(
                                trip_update=trip_update,
                                stop_sequence=stu.stop_sequence
                                if stu.HasField("stop_sequence")
                                else None,
                                stop_id=stu.stop_id
                                if stu.HasField("stop_id")
                                else None,
                                arrival_delay=stu.arrival.delay
                                if stu.arrival.HasField("delay")
                                else None,
                                arrival_time=gtfs_timestamp(stu.arrival.time)
                                if stu.arrival.HasField("time")
                                else None,
                                arrival_uncertainty=stu.arrival.uncertainty
                                if stu.arrival.HasField("uncertainty")
                                else None,
                                departure_delay=stu.departure.delay
                                if stu.departure.HasField("delay")
                                else None,
                                departure_time=gtfs_timestamp(stu.departure.time)
                                if stu.departure.HasField("time")
                                else None,
                                departure_uncertainty=stu.departure.uncertainty
                                if stu.departure.HasField("uncertainty")
                                else None,
                                schedule_relationship=stu.schedule_relationship
                                if stu.HasField("schedule_relationship")
                                else None,
                            )
                        )

                if stop_time_updates_to_create:
                    StopTimeUpdate.objects.bulk_create(
                        stop_time_updates_to_create,
                        batch_size=2000,
                    )

    return "TripUpdates saved to database"


@shared_task
def get_service_alerts():
    return "Fetching Alerts"
