import re
from django.db.models import UniqueConstraint
from django.core.exceptions import ValidationError
from django.contrib.gis.db import models
from django.contrib.gis.geos import Point
from gtfs.models import (
    BaseAgency,
    BaseStop,
    BaseRoute,
    BaseCalendar,
    BaseCalendarDate,
    BaseShape,
    BaseTrip,
    BaseStopTime,
    BaseFareAttribute,
    BaseFareRule,
    BaseFeedInfo,
)


def validate_no_spaces_or_special_symbols(value: str) -> None:
    """Reject identifiers containing characters other than ASCII letters, digits, or underscores."""
    if re.search(r"[^a-zA-Z0-9_]", value):
        raise ValidationError(
            "Este campo no puede contener espacios ni símbolos especiales, solamente letras, números y guiones bajos."
        )


# --------------
# Transit system
# --------------


class TransitSystem(models.Model):
    """A transit system is a collection of GTFS providers that serve a common purpose, for example, the public transportation system of a city or country."""

    name = models.CharField(max_length=255, help_text="Name of the transit system.")
    code = models.CharField(
        max_length=31,
        help_text="Transit system code (typically its acronym). It must not contain spaces or special characters.",
        validators=[validate_no_spaces_or_special_symbols],
        unique=True,
    )
    description = models.TextField(
        blank=True, null=True, help_text="Description of the transit system."
    )
    is_active = models.BooleanField(
        default=False, help_text="Whether the transit system is active."
    )

    def __str__(self):
        return f"{self.code}: {self.name}"


class FeedPublisher(models.Model):
    """Represent a GTFS data publisher for one transit system, potentially distinct from and serving multiple feed agencies, with schedule and realtime endpoints."""

    transit_system = models.ForeignKey(
        TransitSystem,
        help_text="Transit system served by the feed publisher.",
        on_delete=models.CASCADE,
    )
    code = models.CharField(
        max_length=31,
        help_text="Company code (typically its acronym). It must not contain spaces or special characters.",
        validators=[validate_no_spaces_or_special_symbols],
        unique=True,
    )
    name = models.CharField(max_length=255, help_text="Name of the company.")
    description = models.TextField(
        blank=True, null=True, help_text="Description of the institution or company."
    )
    lang = models.CharField(
        max_length=15,
        blank=True,
        null=True,
        help_text="Language of the data provided by the publisher, in ISO 639-1 alpha-2 or alpha-3 format. Examples: es, en, fr.",
    )
    contact_email = models.EmailField(
        blank=True,
        null=True,
        help_text="Contact email address for the data publisher.",
    )
    contact_url = models.URLField(
        blank=True, null=True, help_text="Contact URL for the data publisher."
    )
    website = models.URLField(blank=True, null=True, help_text="Company website.")
    schedule_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL of the GTFS Schedule feed (.zip).",
    )
    trip_updates_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL of the GTFS Realtime TripUpdates FeedMessage (.pb).",
    )
    vehicle_positions_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL of the GTFS Realtime VehiclePositions FeedMessage (.pb).",
    )
    alerts_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL of the GTFS Realtime ServiceAlerts FeedMessage (.pb).",
    )
    timezone = models.CharField(
        max_length=63,
        help_text="Time zone of the data publisher (assumed to be the same for all agencies). Example: America/Costa_Rica.",
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Whether the data publisher is active. If inactive, data from this publisher will not be imported.",
    )

    def __str__(self):
        return f"{self.transit_system.code}: {self.name} ({self.code})"


class Feed(models.Model):
    """Track a retrieved GTFS Schedule feed and its publisher, transit system, validity window, HTTP metadata, version, and current status."""

    feed_id = models.CharField(max_length=100, primary_key=True, unique=True)
    feed_publisher = models.ForeignKey(
        FeedPublisher, on_delete=models.SET_NULL, blank=True, null=True
    )
    transit_system = models.ForeignKey(
        TransitSystem, on_delete=models.SET_NULL, blank=True, null=True
    )
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    version = models.CharField(max_length=255, blank=True, null=True)
    http_etag = models.CharField(max_length=1023, blank=True, null=True)
    http_last_modified = models.DateTimeField(blank=True, null=True)
    is_current = models.BooleanField(blank=True, null=True)
    retrieved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.feed_id


class FeedMessage(models.Model):
    """Record GTFS Realtime header metadata and entity category for a publisher, with newest messages ordered first."""

    ENTITY_TYPE_CHOICES = (
        ("trip_update", "TripUpdate"),
        ("vehicle", "VehiclePosition"),
        ("alert", "Alert"),
    )

    feed_message_id = models.CharField(max_length=63, primary_key=True)
    publisher = models.ForeignKey(
        FeedPublisher, on_delete=models.SET_NULL, blank=True, null=True
    )
    entity_type = models.CharField(max_length=63, choices=ENTITY_TYPE_CHOICES)
    timestamp = models.DateTimeField(auto_now=True)
    incrementality = models.CharField(max_length=15)
    gtfs_realtime_version = models.CharField(max_length=15)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(
                fields=["publisher", "entity_type"],
                name="feedmessage_publisher_type_idx",
            ),
        ]

    def __str__(self):
        return f"{self.entity_type} ({self.timestamp})"


# -------------
# GTFS Schedule
# -------------


class Agency(BaseAgency):
    """Store an agency named in agency.txt and scope its inherited GTFS data to one schedule feed."""

    feed = models.ForeignKey(Feed, to_field="feed_id", on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["feed", "agency_id"], name="unique_agency_in_feed")
        ]
        verbose_name_plural = "agencies"

    def __str__(self):
        return self.agency_name


class Stop(BaseStop):
    """Store a feed-scoped boarding location from stops.txt with an optional heading and a geographic point synchronized with its coordinates."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    stop_point = models.PointField(
        blank=True,
        null=True,
    )
    stop_heading = models.CharField(
        max_length=2,
        blank=True,
        null=True,
        choices=(
            ("N", "north"),
            ("NE", "northeast"),
            ("E", "east"),
            ("SE", "southeast"),
            ("S", "south"),
            ("SW", "southwest"),
            ("W", "west"),
            ("NW", "northwest"),
        ),
    )

    class Meta:
        constraints = [
            UniqueConstraint(fields=["feed", "stop_id"], name="unique_stop_in_feed")
        ]

    # Build stop_point or stop_lat and stop_lon
    def save(self, *args: object, **kwargs: object) -> None:
        """Synchronize the geographic point with latitude and longitude before persisting the stop."""
        if self.stop_point:
            self.stop_lat = self.stop_point.y
            self.stop_lon = self.stop_point.x
        else:
            if self.stop_lon is not None and self.stop_lat is not None:
                try:
                    self.stop_point = Point(float(self.stop_lon), float(self.stop_lat))
                except (TypeError, ValueError):
                    self.stop_point = None
            else:
                self.stop_point = None
        super(Stop, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.stop_id}: {self.stop_name}"


class Route(BaseRoute):
    """Store a feed-scoped rider-facing service imported from routes.txt, including its agency association."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["feed", "route_id"], name="unique_route_in_feed")
        ]

    def __str__(self):
        return f"{self.route_short_name}: {self.route_long_name}"


class Calendar(BaseCalendar):
    """Store a feed-scoped weekly service pattern imported from calendar.txt."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "service_id"], name="unique_service_in_feed"
            )
        ]

    def __str__(self):
        return self.service_id


class CalendarDate(BaseCalendarDate):
    """Store a feed-scoped exception from calendar_dates.txt with an optional holiday or observance name."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    holiday_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        default="Feriado",
        help_text="Name of the holiday or observance.",
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "service_id", "date"], name="unique_date_in_feed"
            )
        ]

    def __str__(self):
        return f"{self.holiday_name} ({self.service_id})"


class Shape(BaseShape):
    """Store a feed-scoped ordered route-shape point imported from shapes.txt."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "shape_id", "shape_pt_sequence"],
                name="unique_shape_in_feed",
            )
        ]

    def __str__(self):
        return f"{self.shape_id}: {self.shape_pt_sequence}"


class Trip(BaseTrip):
    """Store a feed-scoped scheduled journey from trips.txt as a timed sequence of at least two stops."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(fields=["feed", "trip_id"], name="unique_trip_in_feed")
        ]

    def __str__(self):
        return self.trip_id


class StopTime(BaseStopTime):
    """Store a feed-scoped scheduled arrival and departure at one trip stop from stop_times.txt."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "trip_id", "stop_sequence"],
                name="unique_stoptime_in_feed",
            )
        ]

    def __str__(self):
        return f"{self.trip_id}: {self.stop_id} ({self.stop_sequence})"


class FareAttribute(BaseFareAttribute):
    """Store a feed-scoped fare product and its calculation rules imported from fare_attributes.txt."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "fare_id"], name="unique_fareattribute_in_feed"
            )
        ]

    def __str__(self):
        return self.fare_id


class FareRule(BaseFareRule):
    """Store feed-scoped route and zone conditions from fare_rules.txt that determine when a fare applies."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=[
                    "feed",
                    "fare_id",
                    "route_id",
                    "origin_id",
                    "destination_id",
                    "contains_id",
                ],
                name="unique_fare_rule_in_feed",
            )
        ]

    def __str__(self):
        return f"{self.fare_id}: {self.route_id}"


class FeedInfo(BaseFeedInfo):
    """Store publisher, version, language, and validity metadata from feed_info.txt for a schedule feed."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.feed_publisher_name}: {self.feed_version}"


# ----------------
# Auxiliary models
# ----------------


class GeoShape(models.Model):
    """Store a feed-scoped LineString representation of a shapes.txt route with optional labels, endpoints, and altitude metadata."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    shape_id = models.CharField(
        max_length=255, help_text="Unique identifier for the shape."
    )
    geometry = models.LineStringField(
        help_text="Route shape geometry.",
        # dim=3, # To store 3D coordinates (x, y, z)
    )
    shape_name = models.CharField(max_length=255, blank=True, null=True)
    shape_desc = models.TextField(blank=True, null=True)
    shape_from = models.CharField(max_length=255, blank=True, null=True)
    shape_to = models.CharField(max_length=255, blank=True, null=True)
    has_altitude = models.BooleanField(
        help_text="Whether the shape includes altitude data.", default=False
    )

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "shape_id"], name="unique_geoshape_in_feed"
            )
        ]

    def __str__(self):
        return self.shape_id


class RouteStop(models.Model):
    """Describes the sequence of stops for a route and a shape."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    route_id = models.CharField(max_length=200)
    linked_route = models.ForeignKey(
        Route, on_delete=models.CASCADE, blank=True, null=True
    )
    shape_id = models.CharField(max_length=200)
    linked_shape = models.ForeignKey(
        GeoShape, on_delete=models.CASCADE, blank=True, null=True
    )
    direction_id = models.PositiveIntegerField()
    stop_id = models.CharField(max_length=200)
    linked_stop = models.ForeignKey(
        Stop, on_delete=models.CASCADE, blank=True, null=True
    )
    stop_sequence = models.PositiveIntegerField()
    timepoint = models.BooleanField()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "route_id", "shape_id", "stop_sequence"],
                name="unique_routestop_in_feed",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        """Resolve route, geographic shape, and stop foreign keys from their feed-scoped identifiers before saving."""
        self.linked_route = Route.objects.get(feed=self.feed, route_id=self.route_id)
        self.linked_shape = GeoShape.objects.get(feed=self.feed, shape_id=self.shape_id)
        self.linked_stop = Stop.objects.get(feed=self.feed, stop_id=self.stop_id)
        super(RouteStop, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.route_id}: {self.stop_id} ({self.shape_id} {self.stop_sequence})"


class TripDuration(models.Model):
    """Describes the duration of a trip for a route and a service."""

    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    route_id = models.CharField(max_length=200)
    linked_route = models.ForeignKey(
        Route, on_delete=models.CASCADE, blank=True, null=True
    )
    shape_id = models.CharField(max_length=200)
    linked_shape = models.ForeignKey(
        Shape, on_delete=models.CASCADE, blank=True, null=True
    )
    service_id = models.CharField(max_length=200)
    linked_service = models.ForeignKey(
        Calendar, on_delete=models.CASCADE, blank=True, null=True
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    stretch = models.PositiveIntegerField()
    stretch_duration = models.DurationField()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=[
                    "feed",
                    "route_id",
                    "shape_id",
                    "service_id",
                    "start_time",
                    "stretch",
                ],
                name="unique_tripduration_in_feed",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        """Resolve route, shape, and service records from feed-scoped identifiers before persisting a trip-duration row."""
        self.linked_route = Route.objects.get(feed=self.feed, route_id=self.route_id)
        self.linked_shape = Shape.objects.get(feed=self.feed, shape_id=self.shape_id)
        self.linked_service = Calendar.objects.get(
            feed=self.feed, service_id=self.service_id
        )
        super(TripDuration, self).save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.route_id}: {self.service_id} ({self.start_time} - {self.end_time})"
        )


class TripTime(models.Model):
    """
    TODO: llenar cuando se hace el proceso de importación de GTFS. Este modelo se llena con los datos de stop_times.txt, con las filas donde timepoint = True.
    """

    id = models.BigAutoField(primary_key=True)
    feed = models.ForeignKey(Feed, on_delete=models.CASCADE)
    trip_id = models.CharField(max_length=200)
    linked_trip = models.ForeignKey(
        Trip, on_delete=models.CASCADE, blank=True, null=True
    )
    stop_id = models.CharField(max_length=200)
    linked_stop = models.ForeignKey(
        Stop, on_delete=models.CASCADE, blank=True, null=True
    )
    stop_sequence = models.PositiveIntegerField()
    departure_time = models.TimeField()

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["feed", "trip_id", "stop_id"],
                name="unique_triptime_in_feed",
            )
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        """Resolve trip and stop foreign keys from their feed-scoped identifiers before saving a trip timepoint."""
        self.linked_trip = Trip.objects.get(feed=self.feed, trip_id=self.trip_id)
        self.linked_stop = Stop.objects.get(feed=self.feed, stop_id=self.stop_id)
        super(TripTime, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.trip_id}: {self.stop_id} ({self.departure_time})"


# -------------
# GTFS Realtime
# -------------


class TripUpdate(models.Model):
    """Store a normalized GTFS Realtime v2.0 timetable deviation with trip and vehicle descriptors, timestamp, and delay data."""

    id = models.BigAutoField(primary_key=True)
    entity_id = models.CharField(max_length=127, db_index=True)

    # Foreign key to FeedMessage model
    feed_message = models.ForeignKey("FeedMessage", on_delete=models.CASCADE)

    # TripDescriptor (message)
    trip_trip_id = models.CharField(max_length=255, blank=True, null=True)
    trip_route_id = models.CharField(max_length=255, blank=True, null=True)
    trip_direction_id = models.IntegerField(blank=True, null=True)
    trip_start_time = models.DurationField(blank=True, null=True)
    trip_start_date = models.DateField(blank=True, null=True)
    trip_schedule_relationship = models.CharField(
        max_length=31, blank=True, null=True
    )  # (enum)

    # VehicleDescriptor (message)
    vehicle_id = models.CharField(max_length=255, blank=True, null=True)
    vehicle_label = models.CharField(max_length=255, blank=True, null=True)
    vehicle_license_plate = models.CharField(max_length=255, blank=True, null=True)
    vehicle_wheelchair_accessible = models.CharField(
        max_length=31, blank=True, null=True
    )  # (enum)

    # Timestamp (uint64)
    timestamp = models.DateTimeField(blank=True, null=True)

    # Delay (int32)
    delay = models.IntegerField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["trip_trip_id"], name="tripupdate_trip_id_idx"),
            models.Index(fields=["trip_route_id"], name="tripupdate_route_id_idx"),
        ]

    def __str__(self):
        return f"{self.entity_id} ({self.feed_message})"


class StopTimeUpdate(models.Model):
    """Store a normalized GTFS Realtime v2.0 stop update with arrival and departure events linked to a TripUpdate."""

    id = models.BigAutoField(primary_key=True)
    trip_update = models.ForeignKey(TripUpdate, on_delete=models.CASCADE)

    # Stop ID (string)
    stop_sequence = models.IntegerField(blank=True, null=True)
    stop_id = models.CharField(max_length=127, blank=True, null=True)

    # StopTimeEvent (message): arrival
    arrival_delay = models.IntegerField(blank=True, null=True)
    arrival_time = models.DateTimeField(blank=True, null=True)
    arrival_uncertainty = models.IntegerField(blank=True, null=True)

    # StopTimeEvent (message): departure
    departure_delay = models.IntegerField(blank=True, null=True)
    departure_time = models.DateTimeField(blank=True, null=True)
    departure_uncertainty = models.IntegerField(blank=True, null=True)

    # ScheduleRelationship (enum)
    schedule_relationship = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.stop_id} ({self.trip_update})"


class VehiclePosition(models.Model):
    """Store a normalized GTFS Realtime v2.0 vehicle observation with trip, vehicle, position, progress, traffic, and occupancy data."""

    id = models.BigAutoField(primary_key=True)
    entity_id = models.CharField(max_length=127, db_index=True)

    # Foreign key to FeedMessage model
    feed_message = models.ForeignKey(
        FeedMessage, on_delete=models.CASCADE, blank=True, null=True
    )

    # TripDescriptor (message)
    trip_trip_id = models.CharField(max_length=255)
    trip_start_time = models.DurationField(blank=True, null=True)
    trip_start_date = models.DateField(blank=True, null=True)
    trip_route_id = models.CharField(max_length=255, blank=True, null=True)
    trip_direction_id = models.IntegerField(blank=True, null=True)
    trip_schedule_relationship = models.IntegerField(
        blank=True,
        null=True,
        choices=(
            (0, "SCHEDULED"),
            (1, "ADDED"),
            (2, "UNSCHEDULED"),
            (3, "CANCELED"),
            (4, "REPLACEMENT"),
            (5, "DUPLICATED"),
            (6, "NEW"),
            (7, "DELETED"),
        ),
    )  # (enum)

    # VehicleDescriptor (message)
    vehicle_id = models.CharField(max_length=255, blank=True, null=True)
    vehicle_label = models.CharField(max_length=255, blank=True, null=True)
    vehicle_license_plate = models.CharField(max_length=255, blank=True, null=True)
    vehicle_wheelchair_accessible = models.CharField(
        max_length=31, blank=True, null=True
    )  # (enum)

    # Position (message)
    position_latitude = models.FloatField(blank=True, null=True)
    position_longitude = models.FloatField(blank=True, null=True)
    position_point = models.PointField(srid=4326, blank=True, null=True)
    position_bearing = models.FloatField(blank=True, null=True)
    position_odometer = models.FloatField(blank=True, null=True)
    position_speed = models.FloatField(blank=True, null=True)  # (meters/second)

    # Current stop sequence (uint32)
    current_stop_sequence = models.IntegerField(blank=True, null=True)

    # Stop ID (string)
    stop_id = models.CharField(max_length=255, blank=True, null=True)

    # VehicleStopStatus (enum)
    current_status = models.IntegerField(
        blank=True,
        null=True,
        choices=(
            (0, "INCOMING_AT"),
            (1, "STOPPED_AT"),
            (2, "IN_TRANSIT_TO"),
        ),
    )

    # Timestamp (uint64)
    timestamp = models.DateTimeField(blank=True, null=True)

    # CongestionLevel (enum)
    congestion_level = models.IntegerField(
        blank=True,
        null=True,
        choices=(
            (0, "UNKNOWN_CONGESTION_LEVEL"),
            (1, "RUNNING_SMOOTHLY"),
            (2, "STOP_AND_GO"),
            (3, "CONGESTION"),
            (4, "SEVERE_CONGESTION"),
        ),
    )

    # OccupancyStatus (enum)
    occupancy_status = models.IntegerField(
        blank=True,
        null=True,
        choices=(
            (0, "EMPTY"),
            (1, "MANY_SEATS_AVAILABLE"),
            (2, "FEW_SEATS_AVAILABLE"),
            (3, "STANDING_ROOM_ONLY"),
            (4, "CRUSHED_STANDING_ROOM_ONLY"),
            (5, "FULL"),
            (6, "NOT_ACCEPTING_PASSENGERS"),
            (7, "NO_DATA_AVAILABLE"),
            (8, "NOT_BOARDABLE"),
        ),
    )

    # OccupancyPercentage (uint32)
    occupancy_percentage = models.IntegerField(blank=True, null=True)

    # CarriageDetails (message): not implemented

    class Meta:
        indexes = [
            models.Index(fields=["trip_route_id"], name="vehiclepos_route_id_idx"),
            models.Index(fields=["trip_trip_id"], name="vehiclepos_trip_id_idx"),
            models.Index(fields=["timestamp"], name="vehiclepos_timestamp_idx"),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        """Derive the stored geographic point from longitude and latitude before persisting the vehicle observation."""
        if self.position_longitude is not None and self.position_latitude is not None:
            try:
                self.position_point = Point(
                    float(self.position_longitude), float(self.position_latitude)
                )
            except (TypeError, ValueError):
                self.position_point = None
        else:
            self.position_point = None
        super(VehiclePosition, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.entity_id} ({self.feed_message})"


class Alert(models.Model):
    """Store a GTFS Realtime service alert's identifier, feed message, cause, effect, and severity."""
    entity_id = models.CharField(max_length=127, db_index=True)
    feed_message = models.ForeignKey(
        FeedMessage, on_delete=models.CASCADE, blank=True, null=True
    )
    cause = models.IntegerField(
        blank=True,
        null=True,
        choices=(
            (1, "UNKNOWN_CAUSE"),
            (2, "OTHER_CAUSE"),
            (3, "TECHNICAL_PROBLEM"),
            (4, "STRIKE"),
            (5, "DEMONSTRATION"),
            (6, "ACCIDENT"),
            (7, "HOLIDAY"),
            (8, "WEATHER"),
            (9, "MAINTENANCE"),
            (10, "CONSTRUCTION"),
            (11, "POLICE_ACTIVITY"),
            (12, "MEDICAL_EMERGENCY"),
        ),
    )
    effect = models.IntegerField(
        blank=True,
        null=True,
        choices=(
            (1, "NO_SERVICE"),
            (2, "REDUCED_SERVICE"),
            (3, "SIGNIFICANT_DELAYS"),
            (4, "DETOUR"),
            (5, "ADDITIONAL_SERVICE"),
            (6, "MODIFIED_SERVICE"),
            (7, "OTHER_EFFECT"),
            (8, "UNKNOWN_EFFECT"),
            (9, "STOP_MOVED"),
            (10, "NO_EFFECT"),
            (11, "ACCESSIBILITY_ISSUE"),
        ),
    )
    severity_level = models.IntegerField(
        blank=True,
        null=True,
        choices=(
            (1, "UNKNOWN_SEVERITY"),
            (2, "INFO"),
            (3, "WARNING"),
            (4, "SEVERE"),
        ),
    )


class TimeRange(models.Model):
    """Store an optional start and end interval for a service alert's active-period field."""
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, blank=True, null=True)
    field_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=(("active_period", "Active period"),),
    )
    start = models.DateTimeField(blank=True, null=True)
    end = models.DateTimeField(blank=True, null=True)


class EntitySelector(models.Model):
    """Store agency, route, route-type, direction, and stop constraints for an alert's informed entity."""
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, blank=True, null=True)
    field_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=(("informed_entity", "Informed entity"),),
    )
    agency_id = models.CharField(max_length=255, blank=True, null=True)
    route_id = models.CharField(max_length=255, blank=True, null=True)
    route_type = models.IntegerField(blank=True, null=True)
    direction_id = models.IntegerField(blank=True, null=True)
    stop_id = models.CharField(max_length=255, blank=True, null=True)


class TripDescriptor(models.Model):
    """Store trip-instance and schedule-relationship constraints nested under an alert entity selector."""
    entity_selector = models.ForeignKey(
        EntitySelector, on_delete=models.CASCADE, blank=True, null=True
    )
    field_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=(("trip", "Trip"),),
    )
    trip_id = models.CharField(max_length=255, blank=True, null=True)
    route_id = models.CharField(max_length=255, blank=True, null=True)
    direction_id = models.IntegerField(blank=True, null=True)
    start_time = models.DurationField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    schedule_relationship = models.IntegerField(
        blank=True,
        null=True,
        choices=(
            (0, "SCHEDULED"),
            (1, "ADDED"),
            (2, "UNSCHEDULED"),
            (3, "CANCELED"),
            (4, "REPLACEMENT"),
            (5, "DUPLICATED"),
            (6, "NEW"),
            (7, "DELETED"),
        ),
    )


class ModifiedTripSelector(models.Model):
    """Store modification identifiers and replacement timing nested under an alert trip descriptor."""
    trip_descriptor = models.ForeignKey(
        TripDescriptor, on_delete=models.CASCADE, blank=True, null=True
    )
    field_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=(("modified_trip", "Modified trip"),),
    )
    modifications_id = models.CharField(max_length=255, blank=True, null=True)
    affected_trip_id = models.CharField(max_length=255, blank=True, null=True)
    start_time = models.DurationField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)


class TranslatedString(models.Model):
    """Group localized text variants for a selected service-alert text field."""
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, blank=True, null=True)
    field_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=(
            ("cause_detail", "Cause detail"),
            ("effect_detail", "Effect detail"),
            ("url", "URL"),
            ("header_text", "Header text"),
            ("description_text", "Description text"),
            ("tts_header_text", "TTS header text"),
            ("tts_description_text", "TTS description text"),
            ("image_alternative_text", "Image alternative text"),
        ),
    )


class Translation(models.Model):
    """Store localized text and its language for a translated service-alert string."""
    translated_string = models.ForeignKey(
        TranslatedString, on_delete=models.CASCADE, blank=True, null=True
    )
    field_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=(("translation", "Translation"),),
    )
    text = models.TextField(blank=True, null=True)
    language = models.CharField(max_length=15, blank=True, null=True)


class TranslatedImage(models.Model):
    """Group localized image variants for a service alert's image field."""
    alert = models.ForeignKey(Alert, on_delete=models.CASCADE, blank=True, null=True)
    field_name = models.CharField(
        max_length=255, blank=True, null=True, choices=(("image", "Image"),)
    )


class LocalizedImage(models.Model):
    """Store the URL, media type, and language of an image variant attached to a translated alert image."""
    translated_image = models.ForeignKey(
        TranslatedImage, on_delete=models.CASCADE, blank=True, null=True
    )
    field_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        choices=(("localized_image", "Localized image"),),
    )
    url = models.URLField(blank=True, null=True)
    media_type = models.CharField(max_length=255, blank=True, null=True)
    language = models.CharField(max_length=15, blank=True, null=True)
