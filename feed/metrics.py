"""
Prometheus metrics for GTFS data processing.

These metrics track the health and performance of GTFS feed processing:
- Schedule updates
- Vehicle position updates
- Trip updates
- Processing errors
- Processing duration
- Last successful update timestamp
"""

from prometheus_client import Counter, Gauge, Histogram

# Prometheus Metrics for GTFS Processing

GTFS_SCHEDULE_UPDATES_TOTAL = Counter(
    "gtfs_schedule_updates_total",
    "Total number of schedule updates processed",
    ["feed_id"],
)

GTFS_VEHICLE_POSITIONS_UPDATES_TOTAL = Counter(
    "gtfs_vehicle_positions_updates_total",
    "Total number of vehicle position updates processed",
    ["provider"],
)

GTFS_TRIP_UPDATES_TOTAL = Counter(
    "gtfs_trip_updates_total",
    "Total number of trip updates processed",
    ["provider"],
)

GTFS_ENTITIES_PROCESSED_TOTAL = Counter(
    "gtfs_entities_processed_total",
    "Total number of entities processed",
    ["type", "provider"],
)

GTFS_PROCESSING_ERRORS_TOTAL = Counter(
    "gtfs_processing_errors_total",
    "Total number of errors encountered",
    ["task", "provider"],
)

GTFS_LAST_UPDATE_TIMESTAMP = Gauge(
    "gtfs_last_update_timestamp",
    "Timestamp of the last successful update",
    ["type", "provider"],
)

GTFS_PROCESSING_DURATION_SECONDS = Histogram(
    "gtfs_processing_duration_seconds",
    "Time taken to process feed",
    ["type", "provider"],
)
