from django_filters import rest_framework as filters

from feed.models import (
    Agency,
    Alert,
    Calendar,
    CalendarDate,
    FareAttribute,
    FareRule,
    Feed,
    FeedInfo,
    FeedMessage,
    FeedPublisher,
    GeoShape,
    Route,
    Shape,
    Stop,
    StopTime,
    StopTimeUpdate,
    Trip,
    TripUpdate,
    VehiclePosition,
)


class FeedPublisherFilter(filters.FilterSet):
    transit_system = filters.CharFilter(field_name="transit_system__code")

    class Meta:
        model = FeedPublisher
        fields = ["code", "name"]


class FeedFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed_publisher__transit_system__code"
    )

    class Meta:
        model = Feed
        fields = ["feed_id", "feed_publisher", "is_current"]


class AgencyFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = Agency
        fields = ["agency_id", "agency_name"]


class StopFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = Stop
        fields = ["stop_id", "stop_code", "stop_name", "stop_lat", "stop_lon", "stop_url"]


class GeoStopFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = Stop
        fields = ["stop_id", "location_type", "zone_id", "parent_station", "wheelchair_boarding"]


class RouteFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = Route
        fields = ["route_type", "route_id"]


class CalendarFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = Calendar
        fields = ["service_id"]


class CalendarDateFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = CalendarDate
        fields = ["service_id"]


class ShapeFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = Shape
        fields = ["shape_id"]


class GeoShapeFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = GeoShape
        fields = ["shape_id"]


class TripFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = Trip
        fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]


class StopTimeFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = StopTime
        fields = ["trip_id", "stop_id"]


class FeedInfoFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = FeedInfo
        fields = ["feed_publisher_name"]


class FareAttributeFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = FareAttribute
        fields = ["fare_id", "currency_type", "payment_method", "transfers", "agency_id", "feed"]


class FareRuleFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed__feed_publisher__transit_system__code"
    )

    class Meta:
        model = FareRule
        fields = ["fare_id", "route_id", "origin_id", "destination_id", "contains_id", "feed"]


class FeedMessageFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="publisher__transit_system__code"
    )

    class Meta:
        model = FeedMessage
        fields = ["publisher", "entity_type", "incrementality"]


class TripUpdateFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed_message__publisher__transit_system__code"
    )

    class Meta:
        model = TripUpdate
        fields = ["trip_trip_id", "trip_route_id", "trip_start_time", "vehicle_id"]


class StopTimeUpdateFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="trip_update__feed_message__publisher__transit_system__code"
    )

    class Meta:
        model = StopTimeUpdate
        fields = ["stop_id", "stop_sequence", "trip_update", "schedule_relationship"]


class VehiclePositionFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed_message__publisher__transit_system__code"
    )

    class Meta:
        model = VehiclePosition
        fields = [
            "entity_id",
            "feed_message",
            "trip_trip_id",
            "trip_route_id",
            "trip_schedule_relationship",
            "vehicle_id",
            "stop_id",
            "timestamp",
        ]


class ServiceAlertFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed_message__publisher__transit_system__code"
    )

    class Meta:
        model = Alert
        fields = ["entity_id", "cause", "effect", "severity_level", "feed_message"]
