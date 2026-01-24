from feed.models import InfoService
from gtfs.models import *
from alerts.models import *
from .models import UserData, UserReport, WideAlert
from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer, GeometryField

from django.conf import settings
from django.utils import timezone

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
    arrival_time = serializers.DateTimeField(allow_null=True, required=False)
    departure_time = serializers.DateTimeField(allow_null=True, required=False)
    in_progress = serializers.BooleanField()
    progression = ProgressionSerializer(allow_null=True, required=False)


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
    arrival = serializers.DateTimeField(allow_null=True, required=False)
    departure = serializers.DateTimeField(allow_null=True, required=False)


class NextStopSerializer(serializers.Serializer):
    trip_id = serializers.CharField()
    start_date = serializers.DateField()
    start_time = serializers.DurationField()
    next_stop_sequence = NextStopSequenceSerializer(many=True)


class RoutesAtStopSerializer(serializers.Serializer):
    route_id = serializers.CharField(required=False)


class RouteStopPropertiesSerializer(serializers.Serializer):

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
    type = serializers.CharField()
    coordinates = serializers.ListField(child=serializers.FloatField())


class RouteStopFeatureSerializer(serializers.Serializer):
    type = serializers.CharField()
    geometry = RouteStopGeometrySerializer()
    properties = RouteStopPropertiesSerializer()


class RouteStopSerializer(serializers.Serializer):
    type = serializers.CharField()
    features = RouteStopFeatureSerializer(many=True)


class AgencySerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Agency
        fields = "__all__"


class StopSerializer(serializers.HyperlinkedModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Stop
        exclude = ["stop_point"]


class RouteStopsSerializer(serializers.Serializer):
    route_id = serializers.CharField()
    stop_sequence = serializers.IntegerField()
    stop_id = serializers.CharField()
    stop_name = serializers.CharField()
    stop_lat = serializers.FloatField()
    stop_lon = serializers.FloatField()


class GeoStopSerializer(GeoFeatureModelSerializer):

    feed = serializers.PrimaryKeyRelatedField(read_only=True)
    stop_point = GeometryField()

    class Meta:
        model = Stop
        geo_field = "stop_point"
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


class TripTimesSerializer(serializers.Serializer):
    trip_id = serializers.CharField()
    start_time = serializers.CharField()
    end_time = serializers.CharField()
    duration = serializers.IntegerField()


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


class InfoServicePublicSerializer(serializers.ModelSerializer):
    provider = serializers.SerializerMethodField()
    url = serializers.CharField(required=False, allow_null=True)
    active = serializers.BooleanField(required=False)

    class Meta:
        model = InfoService
        fields = ["name", "description", "type", "provider", "url", "active"]

    def get_provider(self, obj):
        provider = getattr(obj, "provider", None)
        return getattr(provider, "name", None)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.setdefault("url", None)
        data.setdefault("active", True)
        return data


class WideAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = WideAlert
        fields = [
            "alert_id",
            "alert_header",
            "alert_description",
            "alert_url",
            "timestamp",
            "source",
        ]


class UserDataSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(required=False, allow_null=True, write_only=True)
    user_email = serializers.EmailField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = UserData
        fields = ["user_id", "user_name", "user_email"]

    def create(self, validated_data):
        validated_data.pop("user_name", None)
        validated_data.pop("user_email", None)
        obj, _created = UserData.objects.get_or_create(user_id=validated_data["user_id"])
        return obj

    def update(self, instance, validated_data):
        return instance


class UserReportLocationSerializer(serializers.Serializer):
    stop_id = serializers.CharField(required=False, allow_blank=False)
    lat = serializers.FloatField(required=False)
    lon = serializers.FloatField(required=False)

    def validate(self, attrs):
        has_stop = bool(attrs.get("stop_id"))
        has_latlon = attrs.get("lat") is not None and attrs.get("lon") is not None
        if has_stop == has_latlon:
            raise serializers.ValidationError(
                "Debe enviar stop_id o (lat, lon) exclusivamente."
            )
        return attrs


class UserEvidenceItemSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["photo", "video", "link", "other"])
    url = serializers.CharField(required=False, allow_null=True)
    b64 = serializers.CharField(required=False, allow_null=True, write_only=True)

    def validate(self, attrs):
        has_url = bool(attrs.get("url"))
        has_b64 = bool(attrs.get("b64"))
        if has_url == has_b64:
            raise serializers.ValidationError("Debe enviar url o b64 exclusivamente.")
        return attrs


class UserReportCreateSerializer(serializers.Serializer):
    report_type = serializers.CharField()
    location = UserReportLocationSerializer()
    description = serializers.CharField(max_length=500)
    user_evidence = UserEvidenceItemSerializer(many=True, required=False)


class UserReportCreatedSerializer(serializers.Serializer):
    report_id = serializers.CharField()
    status = serializers.CharField()


class UserReportSerializer(serializers.ModelSerializer):
    user_id = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    class Meta:
        model = UserReport
        fields = [
            "report_id",
            "user_id",
            "user_name",
            "user_email",
            "report_type",
            "location",
            "description",
            "user_evidence",
            "timestamp",
            "status",
        ]

    def get_user_id(self, obj):
        return None

    def get_user_name(self, obj):
        return None

    def get_user_email(self, obj):
        return None

    def get_location(self, obj):
        if obj.location_stop_id:
            return {"stop_id": obj.location_stop_id}
        if obj.location_lat is not None and obj.location_lon is not None:
            return {"lat": obj.location_lat, "lon": obj.location_lon}
        return None


class WeatherPublicSerializer(serializers.ModelSerializer):
    location = serializers.CharField(source="weather_location")
    timestamp = serializers.SerializerMethodField()

    class Meta:
        model = Weather
        fields = [
            "location",
            "timestamp",
            "temperature",
            "humidity",
            "pressure",
            "wind_speed",
            "wind_direction",
            "precipitation",
            "visibility",
        ]

    def get_timestamp(self, obj):
        # Combine date + time from model
        if not obj.weather_date or not obj.weather_time:
            return None
        from datetime import datetime

        return datetime.combine(obj.weather_date, obj.weather_time)


class SocialPublicSerializer(serializers.ModelSerializer):
    platform = serializers.CharField(source="social_media")
    url = serializers.SerializerMethodField()
    timestamp = serializers.SerializerMethodField()
    content = serializers.CharField(source="social_content")
    source = serializers.SerializerMethodField()

    class Meta:
        model = Social
        fields = ["platform", "url", "timestamp", "content", "source"]

    def get_url(self, obj):
        return None

    def get_timestamp(self, obj):
        if not obj.social_date or not obj.social_time:
            return None
        from datetime import datetime

        return datetime.combine(obj.social_date, obj.social_time)

    def get_source(self, obj):
        return None


class VehiclePositionPublicSerializer(serializers.ModelSerializer):
    vehicle = serializers.SerializerMethodField()
    schedule = serializers.SerializerMethodField()
    timestamp = serializers.SerializerMethodField()
    ttl_seconds = serializers.SerializerMethodField()

    class Meta:
        model = VehiclePosition
        fields = ["vehicle", "schedule", "timestamp", "ttl_seconds"]

    def get_vehicle(self, obj):
        return {
            "id": obj.vehicle_vehicle_id,
            "label": obj.vehicle_vehicle_label,
            "wheelchair_accessible": obj.vehicle_vehicle_wheelchair_accessible,
        }

    def get_schedule(self, obj):
        return {
            "current_stop_sequence": obj.vehicle_current_stop_sequence,
            "stop_id": obj.vehicle_stop_id,
            "current_status": obj.vehicle_current_status,
        }

    def get_timestamp(self, obj):
        return obj.vehicle_timestamp or getattr(getattr(obj, "feed_message", None), "timestamp", None)

    def get_ttl_seconds(self, obj):
        ts = self.get_timestamp(obj)
        if ts is None:
            return 0

        if timezone.is_naive(ts):
            ts = timezone.make_aware(ts)

        ttl_seconds = getattr(settings, "DATAHUB_REALTIME_TTL_SECONDS", 300)
        try:
            ttl_seconds = int(ttl_seconds)
        except (TypeError, ValueError):
            ttl_seconds = 300

        if ttl_seconds <= 0:
            return 0

        age = (timezone.now() - ts).total_seconds()
        remaining = max(0, ttl_seconds - int(age))
        return int(remaining)


class StopTimeEventSerializer(serializers.Serializer):
    time = serializers.DateTimeField(allow_null=True, required=False)
    delay = serializers.IntegerField(allow_null=True, required=False)


class TripUpdateStopTimeUpdateSerializer(serializers.Serializer):
    stop_id = serializers.CharField(allow_null=True, required=False)
    stop_sequence = serializers.IntegerField(allow_null=True, required=False)
    arrival = StopTimeEventSerializer(allow_null=True, required=False)
    departure = StopTimeEventSerializer(allow_null=True, required=False)
    schedule_relationship = serializers.CharField(allow_null=True, required=False)


class TripUpdatePublicSerializer(serializers.ModelSerializer):
    trip_id = serializers.CharField(source="trip_trip_id", allow_null=True, required=False)
    route_id = serializers.CharField(source="trip_route_id", allow_null=True, required=False)
    vehicle_id = serializers.CharField(allow_null=True, required=False)
    ttl_seconds = serializers.SerializerMethodField()
    source = serializers.SerializerMethodField()
    stop_time_update = serializers.SerializerMethodField()

    class Meta:
        model = TripUpdate
        fields = [
            "trip_id",
            "route_id",
            "vehicle_id",
            "timestamp",
            "ttl_seconds",
            "source",
            "stop_time_update",
        ]

    def get_ttl_seconds(self, obj):
        ts = obj.timestamp or getattr(getattr(obj, "feed_message", None), "timestamp", None)
        if ts is None:
            return 0

        if timezone.is_naive(ts):
            ts = timezone.make_aware(ts)

        ttl_seconds = getattr(settings, "DATAHUB_REALTIME_TTL_SECONDS", 300)
        try:
            ttl_seconds = int(ttl_seconds)
        except (TypeError, ValueError):
            ttl_seconds = 300

        if ttl_seconds <= 0:
            return 0

        age = (timezone.now() - ts).total_seconds()
        remaining = max(0, ttl_seconds - int(age))
        return int(remaining)

    def get_source(self, obj):
        return "GTFS-RT"

    def get_stop_time_update(self, obj):
        prefetched = getattr(obj, "stoptimeupdate_set", None)
        if prefetched is not None:
            updates = prefetched.all().order_by("stop_sequence")
        else:
            updates = StopTimeUpdate.objects.filter(trip_update=obj).order_by("stop_sequence")
        items = []
        for u in updates:
            items.append(
                {
                    "stop_id": u.stop_id,
                    "stop_sequence": u.stop_sequence,
                    "arrival": {"time": u.arrival_time, "delay": u.arrival_delay},
                    "departure": {"time": u.departure_time, "delay": u.departure_delay},
                    "schedule_relationship": u.schedule_relationship,
                }
            )
        return items


class ServiceAlertPublicSerializer(serializers.ModelSerializer):
    header_text = serializers.CharField(source="alert_header")
    description_text = serializers.CharField(source="alert_description")
    url = serializers.URLField(source="alert_url", allow_null=True, required=False)
    effect = serializers.SerializerMethodField()
    cause = serializers.SerializerMethodField()
    severity = serializers.SerializerMethodField()
    lifecycle = serializers.SerializerMethodField()
    active_period = serializers.SerializerMethodField()

    class Meta:
        model = Alert
        fields = [
            "alert_id",
            "header_text",
            "description_text",
            "url",
            "effect",
            "cause",
            "severity",
            "lifecycle",
            "active_period",
            "informed_entity",
        ]

    def get_effect(self, obj):
        mapping = {
            2: "DETOUR",
            5: "NO_SERVICE",
        }
        return mapping.get(obj.effect, "OTHER_EFFECT")

    def get_cause(self, obj):
        mapping = {
            2: "ACCIDENT",
            3: "CONGESTION",
            5: "MAINTENANCE",
            6: "CONSTRUCTION",
            10: "STOP_MOVED",
        }
        return mapping.get(obj.cause, "OTHER_CAUSE")

    def get_severity(self, obj):
        mapping = {
            2: "INFO",
            3: "MINOR",
            4: "MAJOR",
            5: "SEVERE",
        }
        return mapping.get(obj.severity, "UNKNOWN")

    def get_active_period(self, obj):
        # Convert date + start/end times to datetimes when possible.
        from datetime import datetime
        from django.utils import timezone

        if not obj.service_date:
            return []

        start_dt = None
        end_dt = None
        if obj.service_start_time:
            start_dt = timezone.make_aware(datetime.combine(obj.service_date, obj.service_start_time))
        if obj.service_end_time:
            end_dt = timezone.make_aware(datetime.combine(obj.service_date, obj.service_end_time))
        return [{"start": start_dt, "end": end_dt}]

    def get_lifecycle(self, obj):
        from django.utils import timezone

        now = timezone.now()
        periods = self.get_active_period(obj)
        if not periods:
            return "UNKNOWN"
        start = periods[0].get("start")
        end = periods[0].get("end")
        if start and now < start:
            return "UPCOMING"
        if end and now > end:
            return "EXPIRED"
        return "ONGOING"
