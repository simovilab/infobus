from zoneinfo import ZoneInfo
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from pathlib import Path
import uuid
import pyarrow as pa
import pyarrow.parquet as pq
import json
from feed.models import VehiclePosition, StopTimeUpdate


def vehicle_positions_to_parquet(use_current_hour=False):
    """Export an hourly window of vehicle positions to a Hive-partitioned GeoParquet file."""
    app_timezone = ZoneInfo(settings.TIME_ZONE)
    now_local = timezone.localtime(timezone.now(), app_timezone)

    if isinstance(use_current_hour, str):
        use_current_hour = use_current_hour.strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
        }

    if use_current_hour:
        window_start = now_local.replace(minute=0, second=0, microsecond=0)
        window_end = window_start + timedelta(hours=1)
    else:
        window_end = now_local.replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=1)

    fields = [
        "id",
        "entity_id",
        "feed_message_id",
        "feed_message__publisher__code",
        "trip_trip_id",
        "trip_route_id",
        "trip_direction_id",
        "trip_start_time",
        "trip_start_date",
        "trip_schedule_relationship",
        "vehicle_id",
        "vehicle_label",
        "vehicle_license_plate",
        "vehicle_wheelchair_accessible",
        "position_latitude",
        "position_longitude",
        "position_point",
        "position_bearing",
        "position_odometer",
        "position_speed",
        "current_stop_sequence",
        "stop_id",
        "current_status",
        "timestamp",
        "congestion_level",
        "occupancy_status",
        "occupancy_percentage",
    ]

    chunk_size = 5000
    row_count = 0
    output_dir = (
        Path("/app/data")
        / "vehicle_positions"
        / f"date={window_start.strftime('%Y-%m-%d')}"
        / f"hour={window_start.strftime('%H')}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"part-{uuid.uuid7()}.parquet"

    geo_metadata = {
        "version": "1.1.0",
        "primary_column": "position",
        "columns": {
            "position": {
                "encoding": "WKB",
                "geometry_types": ["Point"],
                "crs": {
                    "$schema": "https://proj.org/schemas/v0.7/projjson.schema.json",
                    "type": "GeographicCRS",
                    "name": "WGS 84",
                    "datum_ensemble": {
                        "name": "World Geodetic System 1984 ensemble",
                        "members": [
                            {"name": "World Geodetic System 1984 (Transit)"},
                            {"name": "World Geodetic System 1984 (G730)"},
                            {"name": "World Geodetic System 1984 (G873)"},
                            {"name": "World Geodetic System 1984 (G1150)"},
                            {"name": "World Geodetic System 1984 (G1674)"},
                            {"name": "World Geodetic System 1984 (G1762)"},
                            {"name": "World Geodetic System 1984 (G2139)"},
                            {"name": "World Geodetic System 1984 (G2296)"},
                        ],
                        "ellipsoid": {
                            "name": "WGS 84",
                            "semi_major_axis": 6378137,
                            "inverse_flattening": 298.257223563,
                        },
                        "accuracy": "2.0",
                        "id": {"authority": "EPSG", "code": 6326},
                    },
                    "coordinate_system": {
                        "subtype": "ellipsoidal",
                        "axis": [
                            {
                                "name": "Geodetic latitude",
                                "abbreviation": "Lat",
                                "direction": "north",
                                "unit": "degree",
                            },
                            {
                                "name": "Geodetic longitude",
                                "abbreviation": "Lon",
                                "direction": "east",
                                "unit": "degree",
                            },
                        ],
                    },
                    "scope": "Horizontal component of 3D system.",
                    "area": "World.",
                    "bbox": {
                        "south_latitude": -90,
                        "west_longitude": -180,
                        "north_latitude": 90,
                        "east_longitude": 180,
                    },
                    "id": {"authority": "EPSG", "code": 4326},
                },
            }
        },
    }

    parquet_schema = pa.schema(
        [
            pa.field("id", pa.int64()),
            pa.field("entity_id", pa.string()),
            pa.field("feed_message_id", pa.string()),
            pa.field("publisher_code", pa.string()),
            pa.field("trip_id", pa.string()),
            pa.field("route_id", pa.string()),
            pa.field("direction_id", pa.int64()),
            pa.field("start_time", pa.duration("s")),
            pa.field("start_date", pa.date32()),
            pa.field("schedule_relationship", pa.int64()),
            pa.field("vehicle_id", pa.string()),
            pa.field("vehicle_label", pa.string()),
            pa.field("vehicle_license_plate", pa.string()),
            pa.field("wheelchair_accessible", pa.string()),
            pa.field("latitude", pa.float64()),
            pa.field("longitude", pa.float64()),
            pa.field("position", pa.binary()),
            pa.field("bearing", pa.float64()),
            pa.field("odometer", pa.float64()),
            pa.field("speed", pa.float64()),
            pa.field("stop_sequence", pa.int64()),
            pa.field("stop_id", pa.string()),
            pa.field("current_status", pa.int64()),
            pa.field("timestamp", pa.timestamp("us", tz=settings.TIME_ZONE)),
            pa.field("congestion_level", pa.int64()),
            pa.field("occupancy_status", pa.int64()),
            pa.field("occupancy_percentage", pa.int64()),
        ],
        metadata={b"geo": json.dumps(geo_metadata).encode("utf-8")},
    )

    string_columns = {
        "entity_id",
        "feed_message_id",
        "publisher_code",
        "trip_id",
        "route_id",
        "vehicle_id",
        "vehicle_label",
        "vehicle_license_plate",
        "wheelchair_accessible",
        "stop_id",
    }

    writer = None
    batch_rows = []

    def flush_batch(records, parquet_writer):
        """Write a nonempty batch of vehicle-position records and return the active Parquet writer."""
        nonlocal row_count
        if not records:
            return parquet_writer

        arrow_table = pa.Table.from_pylist(records, schema=parquet_schema)
        row_count += arrow_table.num_rows

        if parquet_writer is None:
            parquet_writer = pq.ParquetWriter(
                str(output_file),
                parquet_schema,
                compression="zstd",
            )

        parquet_writer.write_table(arrow_table)
        return parquet_writer

    try:
        queryset = (
            VehiclePosition.objects.filter(
                timestamp__gte=window_start,
                timestamp__lt=window_end,
            )
            .values(*fields)
            .iterator(chunk_size=chunk_size)
        )

        for raw_row in queryset:
            point = raw_row.get("position_point")
            row = {
                "id": raw_row.get("id"),
                "entity_id": raw_row.get("entity_id"),
                "feed_message_id": raw_row.get("feed_message_id"),
                "publisher_code": raw_row.get("feed_message__publisher__code"),
                "trip_id": raw_row.get("trip_trip_id"),
                "route_id": raw_row.get("trip_route_id"),
                "direction_id": raw_row.get("trip_direction_id"),
                "start_time": raw_row.get("trip_start_time"),
                "start_date": raw_row.get("trip_start_date"),
                "schedule_relationship": raw_row.get("trip_schedule_relationship"),
                "vehicle_id": raw_row.get("vehicle_id"),
                "vehicle_label": raw_row.get("vehicle_label"),
                "vehicle_license_plate": raw_row.get("vehicle_license_plate"),
                "wheelchair_accessible": raw_row.get("vehicle_wheelchair_accessible"),
                "latitude": raw_row.get("position_latitude"),
                "longitude": raw_row.get("position_longitude"),
                "position": bytes(point.wkb) if point is not None else None,
                "bearing": raw_row.get("position_bearing"),
                "odometer": raw_row.get("position_odometer"),
                "speed": raw_row.get("position_speed"),
                "stop_sequence": raw_row.get("current_stop_sequence"),
                "stop_id": raw_row.get("stop_id"),
                "current_status": raw_row.get("current_status"),
                "timestamp": raw_row.get("timestamp"),
                "congestion_level": raw_row.get("congestion_level"),
                "occupancy_status": raw_row.get("occupancy_status"),
                "occupancy_percentage": raw_row.get("occupancy_percentage"),
            }

            row_timestamp = row.get("timestamp")
            if row_timestamp is not None:
                row["timestamp"] = timezone.localtime(row_timestamp, app_timezone)

            for column in string_columns:
                value = row.get(column)
                if value is not None and not isinstance(value, str):
                    row[column] = str(value)

            batch_rows.append(row)

            if len(batch_rows) >= chunk_size:
                writer = flush_batch(batch_rows, writer)
                batch_rows = []

        writer = flush_batch(batch_rows, writer)

        if writer is None:
            return (
                "Task completed: VehiclePositions export skipped (no rows) "
                f"({window_start.isoformat()} to {window_end.isoformat()}, "
                f"mode={'current_hour' if use_current_hour else 'last_complete_hour'})"
            )
    finally:
        if writer is not None:
            writer.close()

    return (
        "Task completed: VehiclePositions exported to parquet "
        f"({window_start.isoformat()} to {window_end.isoformat()}, "
        f"mode={'current_hour' if use_current_hour else 'last_complete_hour'}) "
        f"-> {output_file} "
        f"rows={row_count}"
    )


def stop_time_updates_to_parquet(use_current_hour=False):
    """Export an hourly window of stop-time updates to a Hive-partitioned Parquet file."""
    app_timezone = ZoneInfo(settings.TIME_ZONE)
    now_local = timezone.localtime(timezone.now(), app_timezone)

    if isinstance(use_current_hour, str):
        use_current_hour = use_current_hour.strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
        }

    if use_current_hour:
        window_start = now_local.replace(minute=0, second=0, microsecond=0)
        window_end = window_start + timedelta(hours=1)
    else:
        window_end = now_local.replace(minute=0, second=0, microsecond=0)
        window_start = window_end - timedelta(hours=1)

    fields = [
        "id",
        "trip_update__entity_id",
        "trip_update__feed_message_id",
        "trip_update__feed_message__publisher__code",
        "trip_update__timestamp",
        "trip_update__trip_trip_id",
        "trip_update__trip_route_id",
        "trip_update__trip_direction_id",
        "trip_update__trip_start_time",
        "trip_update__trip_start_date",
        "trip_update__trip_schedule_relationship",
        "trip_update__vehicle_id",
        "trip_update__vehicle_label",
        "trip_update__vehicle_license_plate",
        "stop_sequence",
        "stop_id",
        "arrival_delay",
        "arrival_time",
        "arrival_uncertainty",
        "departure_delay",
        "departure_time",
        "departure_uncertainty",
    ]

    chunk_size = 5000
    row_count = 0
    output_dir = (
        Path("/app/data")
        / "stop_time_updates"
        / f"date={window_start.strftime('%Y-%m-%d')}"
        / f"hour={window_start.strftime('%H')}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"part-{uuid.uuid7()}.parquet"

    parquet_schema = pa.schema(
        [
            pa.field("id", pa.int64()),
            pa.field("entity_id", pa.string()),
            pa.field("feed_message_id", pa.string()),
            pa.field("publisher_code", pa.string()),
            pa.field("timestamp", pa.timestamp("us", tz=settings.TIME_ZONE)),
            pa.field("trip_id", pa.string()),
            pa.field("route_id", pa.string()),
            pa.field("direction_id", pa.int64()),
            pa.field("start_time", pa.duration("us")),
            pa.field("start_date", pa.date32()),
            pa.field("schedule_relationship", pa.string()),
            pa.field("vehicle_id", pa.string()),
            pa.field("vehicle_label", pa.string()),
            pa.field("vehicle_license_plate", pa.string()),
            pa.field("stop_sequence", pa.int64()),
            pa.field("stop_id", pa.string()),
            pa.field("arrival_delay", pa.int64()),
            pa.field("arrival_time", pa.timestamp("us", tz=settings.TIME_ZONE)),
            pa.field("arrival_uncertainty", pa.int64()),
            pa.field("arrival_prediction_horizon", pa.int64()),
            pa.field("departure_delay", pa.int64()),
            pa.field("departure_time", pa.timestamp("us", tz=settings.TIME_ZONE)),
            pa.field("departure_uncertainty", pa.int64()),
            pa.field("departure_prediction_horizon", pa.int64()),
        ]
    )

    string_columns = {
        "entity_id",
        "feed_message_id",
        "publisher_code",
        "trip_id",
        "route_id",
        "schedule_relationship",
        "vehicle_id",
        "vehicle_label",
        "vehicle_license_plate",
        "stop_id",
    }

    writer = None
    batch_rows = []

    def flush_batch(records, parquet_writer):
        """Write a nonempty batch of stop-time-update records and return the active Parquet writer."""
        nonlocal row_count
        if not records:
            return parquet_writer

        arrow_table = pa.Table.from_pylist(records, schema=parquet_schema)
        row_count += arrow_table.num_rows

        if parquet_writer is None:
            parquet_writer = pq.ParquetWriter(
                str(output_file),
                parquet_schema,
                compression="zstd",
            )

        parquet_writer.write_table(arrow_table)
        return parquet_writer

    try:
        queryset = (
            StopTimeUpdate.objects.filter(
                trip_update__timestamp__gte=window_start,
                trip_update__timestamp__lt=window_end,
            )
            .values(*fields)
            .iterator(chunk_size=chunk_size)
        )

        for raw_row in queryset:
            row = {
                "id": raw_row.get("id"),
                "entity_id": raw_row.get("trip_update__entity_id"),
                "feed_message_id": raw_row.get("trip_update__feed_message_id"),
                "publisher_code": raw_row.get(
                    "trip_update__feed_message__publisher__code"
                ),
                "timestamp": raw_row.get("trip_update__timestamp"),
                "trip_id": raw_row.get("trip_update__trip_trip_id"),
                "route_id": raw_row.get("trip_update__trip_route_id"),
                "direction_id": raw_row.get("trip_update__trip_direction_id"),
                "start_time": raw_row.get("trip_update__trip_start_time"),
                "start_date": raw_row.get("trip_update__trip_start_date"),
                "schedule_relationship": raw_row.get(
                    "trip_update__trip_schedule_relationship"
                ),
                "vehicle_id": raw_row.get("trip_update__vehicle_id"),
                "vehicle_label": raw_row.get("trip_update__vehicle_label"),
                "vehicle_license_plate": raw_row.get(
                    "trip_update__vehicle_license_plate"
                ),
                "stop_sequence": raw_row.get("stop_sequence"),
                "stop_id": raw_row.get("stop_id"),
                "arrival_delay": raw_row.get("arrival_delay"),
                "arrival_time": raw_row.get("arrival_time"),
                "arrival_uncertainty": raw_row.get("arrival_uncertainty"),
                "arrival_prediction_horizon": (
                    int(
                        (
                            (
                                raw_row.get("arrival_time")
                                - raw_row.get("trip_update__timestamp")
                            ).total_seconds()
                        )
                    )
                    if raw_row.get("arrival_time") is not None
                    and raw_row.get("trip_update__timestamp") is not None
                    else None
                ),
                "departure_delay": raw_row.get("departure_delay"),
                "departure_time": raw_row.get("departure_time"),
                "departure_uncertainty": raw_row.get("departure_uncertainty"),
                "departure_prediction_horizon": (
                    int(
                        (
                            (
                                raw_row.get("departure_time")
                                - raw_row.get("trip_update__timestamp")
                            ).total_seconds()
                        )
                    )
                    if raw_row.get("departure_time") is not None
                    and raw_row.get("trip_update__timestamp") is not None
                    else None
                ),
            }

            row_timestamp = row.get("timestamp")
            if row_timestamp is not None:
                row["timestamp"] = timezone.localtime(row_timestamp, app_timezone)

            arrival_time = row.get("arrival_time")
            if arrival_time is not None:
                row["arrival_time"] = timezone.localtime(arrival_time, app_timezone)

            departure_time = row.get("departure_time")
            if departure_time is not None:
                row["departure_time"] = timezone.localtime(departure_time, app_timezone)

            for column in string_columns:
                value = row.get(column)
                if value is not None and not isinstance(value, str):
                    row[column] = str(value)

            batch_rows.append(row)

            if len(batch_rows) >= chunk_size:
                writer = flush_batch(batch_rows, writer)
                batch_rows = []

        writer = flush_batch(batch_rows, writer)

        if writer is None:
            return (
                "Task completed: StopTimeUpdates export skipped (no rows) "
                f"({window_start.isoformat()} to {window_end.isoformat()}, "
                f"mode={'current_hour' if use_current_hour else 'last_complete_hour'})"
            )
    finally:
        if writer is not None:
            writer.close()

    return (
        "Task completed: StopTimeUpdates exported to parquet "
        f"({window_start.isoformat()} to {window_end.isoformat()}, "
        f"mode={'current_hour' if use_current_hour else 'last_complete_hour'}) "
        f"-> {output_file} "
        f"rows={row_count}"
    )
