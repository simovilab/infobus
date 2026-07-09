from django.contrib.gis.db import models
from runs.domain.lifecycle import RunLifecycleStates, choices
import uuid

# Create your models here.


class Run(models.Model):
    """A run is an instance of GTFS trip."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)

    # Operational information
    vehicle = models.CharField(max_length=100, blank=True, null=True)
    operator = models.CharField(max_length=100, blank=True, null=True)

    # GTFS Schedule information
    route_id = models.CharField(max_length=100, blank=True, null=True)
    trip_id = models.CharField(max_length=100, blank=True, null=True)
    direction_id = models.PositiveSmallIntegerField(blank=True, null=True)
    shape_id = models.CharField(max_length=100, blank=True, null=True)

    # Run information
    request_timestamp = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    start_time = models.DurationField(blank=True, null=True)
    schedule_relationship = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        choices=[
            ("SCHEDULED", "Scheduled in GTFS"),
            ("ADDED", "Added to schedule"),
            ("UNSCHEDULED", "Unscheduled"),
            ("CANCELED", "Canceled"),
            ("DUPLICATED", "Duplicated"),
            ("DELETED", "Deleted"),
        ],
    )
    run_lifecycle_state = models.CharField(
        max_length=40,
        blank=True,
        null=True,
        choices=choices,
        default=RunLifecycleStates.REQUESTED,
    )
    last_event_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.route_id} / {self.trip_id} ({self.start_date})"


"""
Mapping: GTFS-RT VehiclePosition entities → Redis keys

Ownership is visible in the namespace:
  Edge-sensed  → vehicle:<vehicle_id>:*   (written by MQTT consumer)
  Server-computed → run:<run_id>:*        (written by lifecycle actions / progression step)

Position (vehicle:<vehicle_id>:position)
    Producer: edge (MQTT)
    Fields:   latitude, longitude, bearing?, speed?, odometer?, timestamp
    Note:     VehiclePosition.timestamp is lifted from this hash by the builder;
              it is NOT included inside the GTFS-RT Position sub-message.

OccupancyStatus (vehicle:<vehicle_id>:occupancy)
    Producer: edge (MQTT) for raw counts; server buckets the enum at ingestion.
    Fields:   occupancy_percentage?, occupancy_count?, occupancy_status (enum)

VehicleDescriptor / metadata (vehicle:<vehicle_id>:metadata)
    Producer: server (lifecycle action on run start)
    Fields:   id, label, license_plate?, wheelchair_accessible?

TripDescriptor (run:<run_id>:trip)
    Producer: server (lifecycle action — GTFS-RT-shaped projection of run:<id> hash)
    Fields:   trip_id, route_id, direction_id?, schedule_relationship?, start_time?, start_date?

VehicleStopStatus (run:<run_id>:vehicle_stop_status)
    Producer: server (progression step — map-matching position against assigned trip stops)
    Fields:   current_stop_sequence?, stop_id?, current_status (enum)
    Note:     Run-keyed because stop identity requires the assigned trip; not a raw sensor value.

CongestionLevel (run:<run_id>:congestion_level)
    Producer: server (deferred — producer not yet implemented; key reserved)
    Fields:   congestion_level (enum)

Run assignment record (run:<run_id>)
    Producer: server (lifecycle action)
    Fields:   trip_id, route_id, direction_id, shape_id, schedule_relationship,
              start_time, start_date, vehicle, operator, run_lifecycle_state, …
    Note:     run:<id>:trip is the GTFS-RT-shaped projection of its trip subset.

Stale detection:  runs:last_seen:<run_id>  (string, ISO-8601 timestamp)
Active-run sets:  runs:in_progress,  runs:tracking

DECOMMISSIONED:
    vehicle:<vehicle_id>:progression — removed; data split into
    run:<run_id>:vehicle_stop_status (stop fields) and run:<run_id>:congestion_level.

Not mapped:
    multi_carriage_details (omitted)
"""
