from engine.models import InfoService
from feed.models import *
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer, GeometryField

# from gtfs.models import FeedPublisher, Route, Trip, StopTime, Stop, FeedInfo, Calendar, CalendarDate, Shape, GeoShape, FareAttribute, FareRule, ServiceAlert, FeedMessage, TripUpdate, StopTimeUpdate, VehiclePosition, Agency


class FeedPublisherSerializer(serializers.HyperlinkedModelSerializer):
    """Expose all GTFS feed-publisher fields through hyperlinked API representations."""
    class Meta:
        model = FeedPublisher
        fields = "__all__"


class ProgressionSerializer(serializers.Serializer):
    """Represent live vehicle progress along a shape with stop-sequence, status, and occupancy data."""
    position_in_shape = serializers.FloatField()
    current_stop_sequence = serializers.IntegerField()
    current_status = serializers.CharField()
    occupancy_status = serializers.CharField()


class NextArrivalSerializer(serializers.Serializer):
    """Represent route, timing, accessibility, and live progression data for an upcoming arrival."""
    trip_id = serializers.CharField()
    route_id = serializers.CharField()
    route_short_name = serializers.CharField()
    route_long_name = serializers.CharField()
    trip_headsign = serializers.CharField()
    wheelchair_accessible = serializers.CharField()
    arrival_time = serializers.DateTimeField()
    departure_time = serializers.DateTimeField()
    in_progress = serializers.BooleanField()
    progression = ProgressionSerializer()


class NextTripSerializer(serializers.Serializer):
    """Package a stop and query timestamp with its upcoming arrival collection."""
    stop_id = serializers.CharField()
    timestamp = serializers.DateTimeField()
    next_arrivals = NextArrivalSerializer(many=True)


class NextStopSequenceSerializer(serializers.Serializer):
    """Represent an upcoming stop with sequence, location, and predicted arrival and departure times."""
    stop_sequence = serializers.IntegerField()
    stop_id = serializers.CharField()
    stop_name = serializers.CharField()
    stop_lat = serializers.FloatField()
    stop_lon = serializers.FloatField()
    arrival = serializers.DateTimeField()
    departure = serializers.DateTimeField()


class NextStopSerializer(serializers.Serializer):
    """Package a trip instance with its ordered upcoming stop predictions."""
    trip_id = serializers.CharField()
    start_date = serializers.DateField()
    start_time = serializers.DurationField()
    next_stop_sequence = NextStopSequenceSerializer(many=True)


class RoutesAtStopSerializer(serializers.Serializer):
    """Represent an optional route identifier associated with a stop."""
    route_id = serializers.CharField(required=False)


class RouteStopPropertiesSerializer(serializers.Serializer):
    """Represent route, shape, stop, sequencing, timing-point, and accessibility properties for a map feature."""
    route_id = serializers.CharField()
    shape_id = serializers.CharField()
    stop_id = serializers.CharField()
    stop_name = serializers.CharField()
    # stop_heading = serializers.CharField(required=False, allow_blank=True)
    stop_desc = serializers.CharField()
    stop_sequence = serializers.IntegerField()
    timepoint = serializers.BooleanField()
    wheelchair_boarding = serializers.IntegerField(required=False)
    # shelter = serializers.BooleanField(required=False)
    # bench = serializers.BooleanField(required=False)
    # lit = serializers.BooleanField(required=False)
    # bay = serializers.BooleanField(required=False)
    # device_charging_station = serializers.BooleanField(required=False)
    # other_routes = RoutesAtStopSerializer(many=True, required=False)


class RouteStopGeometrySerializer(serializers.Serializer):
    """Represent a GeoJSON geometry type with numeric coordinates."""
    type = serializers.CharField()
    coordinates = serializers.ListField(child=serializers.FloatField())


class RouteStopFeatureSerializer(serializers.Serializer):
    """Combine route-stop geometry and transit properties into a GeoJSON feature."""
    type = serializers.CharField()
    geometry = RouteStopGeometrySerializer()
    properties = RouteStopPropertiesSerializer()


class RouteStopSerializer(serializers.Serializer):
    """Package route-stop features into a GeoJSON feature collection."""
    type = serializers.CharField()
    features = RouteStopFeatureSerializer(many=True)


class AgencySerializer(serializers.HyperlinkedModelSerializer):
    """Expose agency fields with feed ownership represented as a read-only primary-key reference."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Agency
        fields = "__all__"


class StopSerializer(serializers.HyperlinkedModelSerializer):
    """Expose stop fields with feed ownership represented as a read-only primary-key reference."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Stop
        fields = "__all__"


class GeoStopSerializer(GeoFeatureModelSerializer):
    """Transform stop records into GeoJSON features using stop-point geometry and a read-only feed reference."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)
    stop_point = GeometryField()

    class Meta:
        model = Stop
        geo_field = "stop_point"
        fields = "__all__"


class RouteSerializer(serializers.HyperlinkedModelSerializer):
    """Expose route fields while keeping feed ownership read-only."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Route
        fields = "__all__"


class CalendarSerializer(serializers.HyperlinkedModelSerializer):
    """Expose service-calendar fields while keeping feed ownership read-only."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Calendar
        fields = "__all__"


class CalendarDateSerializer(serializers.HyperlinkedModelSerializer):
    """Expose service-exception-date fields while keeping feed ownership read-only."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = CalendarDate
        fields = "__all__"


class ShapeSerializer(serializers.HyperlinkedModelSerializer):
    """Expose scheduled shape-point fields while keeping feed ownership read-only."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Shape
        fields = "__all__"


class GeoShapeSerializer(GeoFeatureModelSerializer):
    """Transform geographic shape records into GeoJSON features with a read-only feed reference."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)
    geometry = GeometryField()

    class Meta:
        model = GeoShape
        geo_field = "geometry"
        fields = "__all__"


class TripSerializer(serializers.HyperlinkedModelSerializer):
    """Expose scheduled-trip fields while keeping feed ownership read-only."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Trip
        fields = "__all__"


class StopTimeSerializer(serializers.HyperlinkedModelSerializer):
    """Expose scheduled stop-time fields while keeping feed ownership read-only."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StopTime
        fields = "__all__"


class FeedInfoSerializer(serializers.HyperlinkedModelSerializer):
    """Expose feed-metadata fields while keeping the associated feed read-only."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FeedInfo
        fields = "__all__"


class FareAttributeSerializer(serializers.HyperlinkedModelSerializer):
    """Expose fare-product attributes while keeping feed ownership read-only."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FareAttribute
        fields = "__all__"


class FareRuleSerializer(serializers.HyperlinkedModelSerializer):
    """Expose fare applicability rules while keeping feed ownership read-only."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FareRule
        fields = "__all__"


class ServiceAlertSerializer(serializers.HyperlinkedModelSerializer):
    """Expose service-alert fields while keeping feed ownership read-only."""
    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Alert
        fields = "__all__"


class FeedMessageSerializer(serializers.HyperlinkedModelSerializer):
    """Expose feed-message fields with the declared provider relation represented by a read-only primary key."""
    provider = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FeedMessage
        fields = "__all__"


class TripUpdateSerializer(serializers.HyperlinkedModelSerializer):
    """Expose trip-update fields with the parent feed message represented by a read-only primary key."""
    feed_message = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TripUpdate
        fields = "__all__"


class StopTimeUpdateSerializer(serializers.HyperlinkedModelSerializer):
    """Expose stop-time-update fields with the parent trip update represented by a read-only primary key."""
    trip_update = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StopTimeUpdate
        fields = "__all__"


class VehiclePositionSerializer(serializers.HyperlinkedModelSerializer):
    """Expose vehicle-position fields with the parent feed message represented by a read-only primary key."""
    feed_message = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = VehiclePosition
        fields = "__all__"


class InfoServiceSerializer(serializers.HyperlinkedModelSerializer):
    """Expose all connected information-service fields through hyperlinked API representations."""
    class Meta:
        model = InfoService
        fields = "__all__"
