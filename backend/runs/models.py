from django.contrib.gis.db import models
from runs.domain.lifecycle import RunLifecycleStates, choices
from feed.models import FeedPublisher
import uuid

# Create your models here.


class Run(models.Model):
    """A run is an instance of GTFS trip."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    feed_publisher = models.ForeignKey(
        FeedPublisher, on_delete=models.CASCADE, related_name="runs"
    )

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
        default=RunLifecycleStates.IN_PROGRESS,
    )
    last_event_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"{self.route_id} / {self.trip_id} ({self.start_date})"


"""
Mapping: GTFS-RT VehiclePosition entities → Redis keys

Ownership is visible in the namespace:
  Edge-sensed  → vehicle:<vehicle_id>:*   (written by MQTT consumer)
  Server-computed → run:<run_id>:*        (written by lifecycle actions / progression step)

OccupancyStatus (vehicle:<vehicle_id>:occupancy)
    Producer: edge (MQTT) for raw counts; server buckets the enum at ingestion.
    Fields:   occupancy_percentage?, occupancy_count?, occupancy_status (enum)

VehicleDescriptor / metadata (vehicle:<vehicle_id>:metadata)
    Producer: server (lifecycle action on run start)
    Fields:   id, label, license_plate?, wheelchair_accessible?

TripDescriptor (run:<run_id>:trip)
    Producer: server (lifecycle action — GTFS-RT-shaped projection of run:<id> hash)
    Fields:   trip_id, route_id, direction_id?, schedule_relationship?, start_time?, start_date?

--- Keys to update on run registration (run metadata)

Runs in progress 

    | Key | Value |
    |---|---|
    |Key | `runs:in_progress` |
    |Redis data type |   set|
    |Values |  run_id|

Trip 
    Key: run:<run_id>:trip
    Redis data type:     hash
    GTFS Message:        TripDescriptor
    Fields:         trip_id, route_id, direction_id?, schedule_relationship?, start_time?, start_date?

Vehicle 
    Redis key: run:<run_id>:vehicle
    Redis data type:       hash
    GTFS Message:    VehicleDescriptor
    Fields:     id?, label?, license_plate?, wheelchair_accessible?

--- Keys to update for each run on each fetch (run states)

Position
    Key: run:<run_id>:position
    Type: hash
    GTFS Message: Position
    Fields:   latitude, longitude, bearing?, odometer?, speed?

Current stop sequence 
    Key: run:<run_id>:current_stop_sequence
    Redis data type:   string
    GTFS Value:  current_stop_sequence (int)

Stop ID (run:<run_id>:stop_id)
    Type:   string
    Value:  stop_id (string)

Current status (run:<run_id>:current_status) 
    Type:   string
    Value:  current_status (enum VehicleStopStatus)

Timestamp (run:<run_id>:timestamp) 
    Type:   string
    Value:  timestamp (ISO-8601 string)

Congestion level (run:<run_id>:congestion_level) 
    Type:   string
    Fields: congestion_level (enum CongestionLevel)

Occupancy status (run:<run_id>:occupancy_status) 
    Type:   string
    Fields: occupancy_status (enum OccupancyStatus)

Occupancy percentage (run:<run_id>:occupancy_percentage)
    Type:   string
    Value:  occupancy_percentage (int)

Stop time updates (run:<run_id>:stop_time_updates)
    Type:   JSON
    Value:  stop_time_updates (message StopTimeUpdate)

Trip properties (run:<run_id>:trip_properties)
    Type:   JSON
    Value:  trip_properties (message TripProperties)

Carriage details (run:<run_id>:multi_carriage_details)
    Type:   JSON
    Value:  multi_carriage_details (message CarriageDetails)

---    

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
