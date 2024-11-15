from feed.models import InfoService
from gtfs.models import *
from alerts.models import *
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer, GeometryField

# from gtfs.models import GTFSProvider, Route, Trip, StopTime, Stop, FeedInfo, Calendar, CalendarDate, Shape, GeoShape, FareAttribute, FareRule, ServiceAlert, Weather, Social, FeedMessage, TripUpdate, StopTimeUpdate, VehiclePosition, Agency


class GTFSProviderSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = GTFSProvider
        fields = "__all__"


class ProgressionSerializer(serializers.Serializer):
    position_in_shape = serializers.FloatField()
    current_stop_sequence = serializers.IntegerField()
    current_status = serializers.CharField()
    occupancy_status = serializers.CharField()


class NextArrivalSerializer(serializers.Serializer):
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
    stop_id = serializers.CharField()
    timestamp = serializers.DateTimeField()
    next_arrivals = NextArrivalSerializer(many=True)


class NextStopSequenceSerializer(serializers.Serializer):
    stop_sequence = serializers.IntegerField()
    stop_id = serializers.CharField()
    stop_name = serializers.CharField()
    stop_lat = serializers.FloatField()
    stop_lon = serializers.FloatField()
    arrival = serializers.DateTimeField()
    departure = serializers.DateTimeField()


class NextStopSerializer(serializers.Serializer):
    trip_id = serializers.CharField()
    start_date = serializers.DateField()
    start_time = serializers.DurationField()
    next_stop_sequence = NextStopSequenceSerializer(many=True)


class AgencySerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Agency
        fields = "__all__"


class StopSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Stop
        fields = "__all__"


class RouteSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Route
        fields = "__all__"


class CalendarSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Calendar
        fields = "__all__"


class CalendarDateSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = CalendarDate
        fields = "__all__"


class ShapeSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Shape
        fields = "__all__"


class GeoShapeSerializer(GeoFeatureModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)
    geometry = GeometryField()

    class Meta:
        model = GeoShape
        geo_field = "geometry"
        fields = "__all__"


class TripSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Trip
        fields = "__all__"


class StopTimeSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StopTime
        fields = "__all__"


class FeedInfoSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FeedInfo
        fields = "__all__"


class FareAttributeSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FareAttribute
        fields = "__all__"


class FareRuleSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FareRule
        fields = "__all__"


class ServiceAlertSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Alert
        fields = "__all__"


class WeatherSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Weather
        fields = "__all__"


class SocialSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Social
        fields = "__all__"


class FeedMessageSerializer(serializers.HyperlinkedModelSerializer):

    provider = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = FeedMessage
        fields = "__all__"


class TripUpdateSerializer(serializers.HyperlinkedModelSerializer):

    feed_message = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = TripUpdate
        fields = "__all__"


class StopTimeUpdateSerializer(serializers.HyperlinkedModelSerializer):

    trip_update = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = StopTimeUpdate
        fields = "__all__"


class VehiclePositionSerializer(serializers.HyperlinkedModelSerializer):

    feed_message = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = VehiclePosition
        fields = "__all__"


class InfoServiceSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = InfoService
        fields = "__all__"
