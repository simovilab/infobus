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
    Alert,
    TimeRange,
    EntitySelector,
    TripDescriptor,
    ModifiedTripSelector,
    TranslatedString,
    Translation,
    TranslatedImage,
    LocalizedImage,
)
from django.contrib.gis.geos import Point

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

                    if table_name == "feed_info" and not table.empty:
                        feed_info_row = table.iloc[0]
                        feed_updates = {}

                        start_date = gtfs_date(
                            normalize_gtfs_value(feed_info_row.get("feed_start_date"))
                        )
                        if start_date is not None:
                            feed_updates["start_date"] = start_date

                        end_date = gtfs_date(
                            normalize_gtfs_value(feed_info_row.get("feed_end_date"))
                        )
                        if end_date is not None:
                            feed_updates["end_date"] = end_date

                        version = normalize_gtfs_value(
                            feed_info_row.get("feed_version")
                        )
                        if version is not None:
                            feed_updates["version"] = version

                        if feed_updates:
                            for field, value in feed_updates.items():
                                setattr(feed, field, value)
                            feed.save(update_fields=list(feed_updates.keys()))

                    table = table[[col for col in fields if col in table.columns]]
                    table["feed"] = feed
                    instances = [
                        model(
                            **{
                                key: normalize_gtfs_value(value)
                                for key, value in row.items()
                            }
                        )
                        for row in table.to_dict(orient="records")
                    ]
                    model.objects.bulk_create(instances, batch_size=2000)
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
                    position_point=Point(v.position.longitude, v.position.latitude)
                    if v.position.HasField("longitude")
                    and v.position.HasField("latitude")
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
def get_alerts():
    def has_optional_field(message, field_name):
        descriptor = getattr(message, "DESCRIPTOR", None)
        if descriptor is None or field_name not in descriptor.fields_by_name:
            return False
        try:
            return message.HasField(field_name)
        except ValueError:
            return False

    publishers = FeedPublisher.objects.filter(is_active=True)
    for publisher in publishers:
        alerts = gtfs_rt.FeedMessage()
        try:
            alerts_response = requests.get(publisher.alerts_url, timeout=10)
            print(f"Fetching alerts from {publisher.alerts_url}")
            alerts.ParseFromString(alerts_response.content)
        except requests.RequestException as e:
            print(f"Error fetching alerts from {publisher.alerts_url}: {str(e)}")
            continue

        # Save FeedMessage object
        feed_message = FeedMessage(
            feed_message_id=f"{publisher.code}-alerts-{alerts.header.timestamp}",
            publisher=publisher,
            entity_type="alert",
            timestamp=gtfs_timestamp(
                alerts.header.timestamp,
                timezone=pytz.timezone(publisher.timezone),
            ),
            incrementality=alerts.header.incrementality,
            gtfs_realtime_version=alerts.header.gtfs_realtime_version,
        )
        feed_message.save()

        # Save Alert entities and their related InformedEntity, TripDescriptor, ModifiedTripSelector, TranslatedString, Translation, and TranslatedImage objects
        entities = alerts.entity
        incoming_entity_ids = [entity.id for entity in entities]
        existing_entity_ids = set(
            Alert.objects.filter(entity_id__in=incoming_entity_ids).values_list(
                "entity_id", flat=True
            )
        )

        for entity in entities:
            if entity.id in existing_entity_ids:
                continue

            a = entity.alert
            with transaction.atomic():
                alert = Alert.objects.create(
                    entity_id=entity.id,
                    feed_message=feed_message,
                    cause=a.cause if a.HasField("cause") else None,
                    effect=a.effect if a.HasField("effect") else None,
                    severity_level=a.severity_level
                    if a.HasField("severity_level")
                    else None,
                )

                # active_period can contain multiple ranges per alert.
                time_ranges_to_create = [
                    TimeRange(
                        alert=alert,
                        field_name="active_period",
                        start=gtfs_timestamp(period.start)
                        if period.HasField("start")
                        else None,
                        end=gtfs_timestamp(period.end)
                        if period.HasField("end")
                        else None,
                    )
                    for period in a.active_period
                ]
                if time_ranges_to_create:
                    TimeRange.objects.bulk_create(time_ranges_to_create, batch_size=500)

                # informed_entity can contain multiple selectors per alert.
                entity_selectors_to_create = []
                trip_protos = []
                for ie in a.informed_entity:
                    entity_selectors_to_create.append(
                        EntitySelector(
                            alert=alert,
                            field_name="informed_entity",
                            agency_id=ie.agency_id
                            if ie.HasField("agency_id")
                            else None,
                            route_id=ie.route_id if ie.HasField("route_id") else None,
                            route_type=ie.route_type
                            if ie.HasField("route_type")
                            else None,
                            direction_id=ie.direction_id
                            if ie.HasField("direction_id")
                            else None,
                            stop_id=ie.stop_id if ie.HasField("stop_id") else None,
                        )
                    )
                    trip_protos.append(ie.trip if ie.HasField("trip") else None)

                if entity_selectors_to_create:
                    created_selectors = EntitySelector.objects.bulk_create(
                        entity_selectors_to_create, batch_size=500
                    )

                    trip_descriptors_to_create = []
                    modified_trip_protos = []
                    for es, trip_proto in zip(created_selectors, trip_protos):
                        if trip_proto is None:
                            continue
                        trip_descriptors_to_create.append(
                            TripDescriptor(
                                entity_selector=es,
                                field_name="trip",
                                trip_id=trip_proto.trip_id
                                if trip_proto.HasField("trip_id")
                                else None,
                                route_id=trip_proto.route_id
                                if trip_proto.HasField("route_id")
                                else None,
                                direction_id=trip_proto.direction_id
                                if trip_proto.HasField("direction_id")
                                else None,
                                start_time=gtfs_time(trip_proto.start_time)
                                if trip_proto.HasField("start_time")
                                else None,
                                start_date=gtfs_date(trip_proto.start_date)
                                if trip_proto.HasField("start_date")
                                else None,
                                schedule_relationship=trip_proto.schedule_relationship
                                if trip_proto.HasField("schedule_relationship")
                                else None,
                            )
                        )
                        try:
                            modified_trip_protos.append(
                                trip_proto.modified_trip
                                if trip_proto.HasField("modified_trip")
                                else None
                            )
                        except ValueError:
                            modified_trip_protos.append(None)

                    if trip_descriptors_to_create:
                        created_trip_descriptors = TripDescriptor.objects.bulk_create(
                            trip_descriptors_to_create, batch_size=500
                        )

                        modified_trip_selectors_to_create = [
                            ModifiedTripSelector(
                                trip_descriptor=td,
                                field_name="modified_trip",
                                modifications_id=mts.modifications_id
                                if mts.HasField("modifications_id")
                                else None,
                                affected_trip_id=mts.affected_trip_id
                                if mts.HasField("affected_trip_id")
                                else None,
                                start_time=gtfs_time(mts.start_time)
                                if mts.HasField("start_time")
                                else None,
                                start_date=gtfs_date(mts.start_date)
                                if mts.HasField("start_date")
                                else None,
                            )
                            for td, mts in zip(
                                created_trip_descriptors, modified_trip_protos
                            )
                            if mts is not None
                        ]
                        if modified_trip_selectors_to_create:
                            ModifiedTripSelector.objects.bulk_create(
                                modified_trip_selectors_to_create, batch_size=500
                            )

                # TranslatedString fields and their Translation children
                translated_string_fields = [
                    ("cause_detail", getattr(a, "cause_detail", None)),
                    ("effect_detail", getattr(a, "effect_detail", None)),
                    ("url", getattr(a, "url", None)),
                    ("header_text", getattr(a, "header_text", None)),
                    ("description_text", getattr(a, "description_text", None)),
                    ("tts_header_text", getattr(a, "tts_header_text", None)),
                    (
                        "tts_description_text",
                        getattr(a, "tts_description_text", None),
                    ),
                    (
                        "image_alternative_text",
                        getattr(a, "image_alternative_text", None),
                    ),
                ]
                for field_name, ts_proto in translated_string_fields:
                    if ts_proto is None or not getattr(ts_proto, "translation", None):
                        continue
                    ts = TranslatedString.objects.create(
                        alert=alert, field_name=field_name
                    )
                    Translation.objects.bulk_create(
                        [
                            Translation(
                                translated_string=ts,
                                field_name="translation",
                                text=t.text,
                                language=t.language if t.HasField("language") else None,
                            )
                            for t in ts_proto.translation
                        ],
                        batch_size=500,
                    )

                # TranslatedImage and its LocalizedImage children
                image_proto = getattr(a, "image", None)
                localized_images = (
                    list(image_proto.localized_image)
                    if image_proto is not None
                    and has_optional_field(a, "image")
                    and getattr(image_proto, "localized_image", None)
                    else []
                )
                if localized_images:
                    translated_image = TranslatedImage.objects.create(
                        alert=alert, field_name="image"
                    )
                    LocalizedImage.objects.bulk_create(
                        [
                            LocalizedImage(
                                translated_image=translated_image,
                                field_name="localized_image",
                                url=li.url,
                                media_type=li.media_type,
                                language=li.language
                                if li.HasField("language")
                                else None,
                            )
                            for li in localized_images
                        ],
                        batch_size=500,
                    )

    return "ServiceAlerts saved to database"
