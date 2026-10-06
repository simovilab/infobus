"""Serializers that shape GTFS Schedule data for Infobús Web pages."""

from rest_framework import serializers

from feed.models import Route, Stop


class WebRouteSerializer(serializers.ModelSerializer):
    """Expose the route fields that the Routes and Route pages need."""

    class Meta:
        model = Route
        fields = [
            "route_id",
            "route_short_name",
            "route_long_name",
            "route_desc",
            "route_type",
            "route_color",
            "route_text_color",
        ]


class WebStopSerializer(serializers.ModelSerializer):
    """Expose the stop fields that the Stops and Stop pages need."""

    class Meta:
        model = Stop
        fields = [
            "stop_id",
            "stop_code",
            "stop_name",
            "stop_desc",
            "stop_lat",
            "stop_lon",
            "wheelchair_boarding",
        ]
