import logging
from typing import TYPE_CHECKING
from feed.models import (
    FeedPublisher,
    Feed,
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
import requests
import zipfile
import io
import pandas as pd
from datetime import datetime
import pytz
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from gtfs.utils import gtfs_date, normalize_gtfs_value
from infobus.utils import redact_url

if TYPE_CHECKING:
    from engine.tasks import ScheduleUpdateResult


STOP_HEADING_CODES = {
    "north": "N",
    "northeast": "NE",
    "east": "E",
    "southeast": "SE",
    "south": "S",
    "southwest": "SW",
    "west": "W",
    "northwest": "NW",
}


REQUIRED_SCHEDULE_MEMBERS: tuple[str, ...] = (
    "agency.txt",
    "stops.txt",
    "routes.txt",
    "trips.txt",
    "stop_times.txt",
)


class ScheduleImportError(Exception):
    """Raised when a GTFS Schedule archive cannot be imported completely."""


def normalize_schedule_value(field_name: str, value: object) -> object:
    """Normalize feed values that use a different representation than our models."""
    value = normalize_gtfs_value(value)
    if field_name == "stop_heading" and isinstance(value, str):
        return STOP_HEADING_CODES.get(value.lower(), value.upper())
    return value


logging.basicConfig(
    format="%(levelname)s: %(message)s",
    encoding="utf-8",
    level=logging.INFO,
)


def save_schedule_to_database(
    feed_publisher: FeedPublisher,
    result: "ScheduleUpdateResult",
) -> None:
    """Import a publisher's GTFS Schedule archive when its remote ETag changes."""
    logging.info(
        f"Active feed publisher found: {feed_publisher.name} ({feed_publisher.code}). Proceeding with schedule update."
    )
    schedule_url = feed_publisher.schedule_url

    logging.info(
        f"\n------------\nGTFS Schedule updating session\n{feed_publisher.name}\n{timezone.now()}\nData source: {redact_url(schedule_url)}\n------------"
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
    feed_check = requests.head(
        schedule_url, timeout=settings.HTTP_REQUEST_TIMEOUT_SECONDS
    )
    feed_tag = feed_check.headers["ETag"]

    if not feed_tag == current_feed_tag:
        logging.info(f"Importing new detected GTFS Schedule feed: {feed_tag}")

        # Request feed
        schedule_response = requests.get(
            schedule_url, timeout=settings.HTTP_REQUEST_TIMEOUT_SECONDS
        )
        schedule_zip = zipfile.ZipFile(io.BytesIO(schedule_response.content))

        member_names = set(schedule_zip.namelist())
        missing_members = [
            member
            for member in REQUIRED_SCHEDULE_MEMBERS
            if member not in member_names
        ]
        if missing_members:
            raise ScheduleImportError(
                f"GTFS Schedule archive for {feed_publisher.code} is missing "
                f"required members: {', '.join(missing_members)}. "
                "Nothing was imported."
            )

        last_modified = feed_check.headers["Last-Modified"]
        last_modified = datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
        last_modified = last_modified.replace(tzinfo=pytz.UTC)
        feed_id = (
            f"{feed_publisher.code} ({last_modified.strftime('%Y-%m-%d %H:%M:%S %Z')})"
        )

        # Save new feed record to database with the Feed model
        with transaction.atomic():
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

                        version = normalize_gtfs_value(feed_info_row.get("feed_version"))
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
                                key: normalize_schedule_value(key, value)
                                for key, value in row.items()
                            }
                        )
                        for row in table.to_dict(orient="records")
                    ]
                    model.objects.bulk_create(instances, batch_size=2000)
                    logging.info(f"{file} imported successfully")

        logging.info("Schedule updated successfully")
        result["has_new_feed"][feed_publisher.code] = True

    else:
        logging.info("No new feed detected. Schedule is up to date.")
        result["has_new_feed"][feed_publisher.code] = False
