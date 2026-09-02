from django.conf import settings
from django.db.models import Model, QuerySet
from django.http import FileResponse
from django.http import HttpRequest
from django.views.decorators.http import require_GET
from engine.models import InfoService
from feed.models import (
    Feed,
    FeedPublisher,
    FeedMessage,
    TripUpdate,
    StopTimeUpdate,
    Agency,
    RouteStop,
    Stop,
    Calendar,
    CalendarDate,
    Route,
    Shape,
    GeoShape,
    FareAttribute,
    FareRule,
    Trip,
    StopTime,
    FeedInfo,
    Alert,
    VehiclePosition,
)
from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from datetime import datetime, timedelta
import pytz
from feed.services.queries import get_next_trips

from .serializers import *


class FilterMixin:
    """Provide allowlisted query-parameter filtering for class-level querysets."""
    def get_filtered_queryset(
        self,
        allowed_query_params: list[str],
    ) -> QuerySet[Model]:
        """Filter the configured queryset using only non-null request parameters in the supplied allowlist."""
        queryset = self.queryset
        query_params = self.request.query_params
        filter_args = {
            param: value
            for param, value in query_params.items()
            if param in allowed_query_params and value is not None
        }
        return queryset.filter(**filter_args)


class FeedPublisherViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to GTFS feed publishers with filtering by code or name."""

    queryset = FeedPublisher.objects.all()
    serializer_class = FeedPublisherSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["code", "name"]
    # permission_classes = [permissions.IsAuthenticated]


class NextTripView(APIView):
    """Serve upcoming realtime and scheduled arrivals for a requested stop, transit system, and optional timestamp."""

    throttle_scope = "realtime"

    def get(self, request: Request) -> Response:
        """Validate the stop and optional timestamp, then serialize upcoming arrivals for the selected transit system."""
        tz = pytz.timezone(settings.TIME_ZONE)

        # Validate stop_id
        if not request.query_params.get("stop_id"):
            return Response(
                {
                    "error": "Es necesario especificar el stop_id como parámetro de la solicitud: /next-trips?stop_id=bUCR-0-01, por ejemplo."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        stop_id = request.query_params.get("stop_id")
        try:
            Stop.objects.get(stop_id=stop_id)
        except Stop.DoesNotExist:
            return Response(
                {
                    "error": f"No existe la parada especificada {stop_id} en la base de datos."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if request.query_params.get("timestamp"):
            timestamp = datetime.strptime(
                request.query_params.get("timestamp"), "%Y-%m-%dT%H:%M:%S"
            )
            timestamp = tz.localize(timestamp)
        else:
            timestamp = None

        transit_system = request.query_params.get("transit_system", "default")
        data = get_next_trips(transit_system, stop_id, timestamp)
        if data is None:
            return Response(
                {"error": "No hay servicio disponible para la fecha especificada."},
                status=status.HTTP_204_NO_CONTENT,
            )

        serializer = NextTripSerializer(data)
        return Response(serializer.data)


class NextStopView(APIView):
    """Serve latest stop-time predictions for a trip identified by ID, date, and start time."""

    throttle_scope = "realtime"

    def get(self, request: Request) -> Response:
        """Validate a trip instance descriptor and combine its latest stop-time updates with current-feed stop details."""
        # Get query parameters
        trip_id = request.query_params.get("trip_id")
        start_date = request.query_params.get("start_date")
        start_time = request.query_params.get("start_time")

        if not trip_id or not start_date or not start_time:
            return Response(
                {
                    "error": "Es necesario especificar todos los parámetros de la solicitud, trip_id, start_date y start_time."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        next_stop_sequence = []

        # For trips in progress
        latest_trip_update = FeedMessage.objects.filter(
            entity_type="trip_update"
        ).latest("timestamp")
        trip_update = TripUpdate.objects.filter(
            feed_message=latest_trip_update,
            trip_trip_id=trip_id,
            trip_start_date=start_date,
            trip_start_time=start_time,
        ).first()
        stop_time_updates = StopTimeUpdate.objects.filter(
            trip_update=trip_update
        ).order_by("stop_sequence")

        current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")

        for stop_time_update in stop_time_updates:
            print(f"La parada: {stop_time_update.stop_id}")
            stop = Stop.objects.get(
                stop_id=stop_time_update.stop_id,
                feed=current_feed,
            )
            next_stop_sequence.append(
                {
                    "stop_sequence": stop_time_update.stop_sequence,
                    "stop_id": stop.stop_id,
                    "stop_name": stop.stop_name,
                    "stop_lat": stop.stop_lat,
                    "stop_lon": stop.stop_lon,
                    "arrival": stop_time_update.arrival_time,
                    "departure": stop_time_update.departure_time,
                }
            )

        data = {
            "trip_id": trip_id,
            "start_date": start_date,
            "start_time": str_to_timedelta(start_time),
            "next_stop_sequence": next_stop_sequence,
        }

        serializer = NextStopSerializer(data)

        return Response(serializer.data)


class RouteStopView(APIView):
    """Serve route-and-shape stop sequences as GeoJSON features."""

    throttle_scope = "realtime"

    def get(self, request: Request) -> Response:
        """Validate route and shape identifiers, then combine indexed stops with current-feed geometry and properties."""
        # Get and validate query parameters
        if request.query_params.get("route_id") and request.query_params.get(
            "shape_id"
        ):
            route_id = request.query_params.get("route_id")
            shape_id = request.query_params.get("shape_id")
            try:
                route_stops = RouteStop.objects.filter(
                    route_id=route_id, shape_id=shape_id
                )
            except RouteStop.DoesNotExist:
                return Response(
                    {
                        "error": f"No existe la combinación de ruta {route_id} y trayectoria {shape_id} en la base de datos."
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            return Response(
                {
                    "error": "Es necesario especificar el route_id y el shape_id como parámetros de la solicitud. Por ejemplo: /route-stops?route_id=bUCR_L1&shape_id=hacia_educacion"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the current GTFS feed
        current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")

        # Construct the GeoJSON structure
        geojson = {"type": "FeatureCollection", "features": []}

        # Build the response for scheduled trips
        for route_stop in route_stops:
            stop = Stop.objects.get(stop_id=route_stop.stop_id, feed=current_feed)

            print(stop.shelter)
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [stop.stop_point.x, stop.stop_point.y],
                },
                "properties": {
                    "route_id": route_stop.route_id,
                    "shape_id": route_stop.shape_id,
                    "stop_id": stop.stop_id,
                    "stop_name": stop.stop_name,
                    # "stop_heading": stop.stop_heading,
                    "stop_desc": stop.stop_desc,
                    "stop_sequence": route_stop.stop_sequence,
                    "timepoint": route_stop.timepoint,
                    "wheelchair_boarding": 1,  # stop.wheelchair_boarding,
                    # "shelter": True,  # stop.shelter,
                    # "bench": True,  # stop.bench,
                    # "lit": True,  # stop.lit,
                    # "bay": True,  # stop.bay,
                    # "device_charging_station": True,  # stop.device_charging_station,
                    # "other_routes": [{"route_id": "adiós"}, {"route_id": "adiós"}],
                },
            }

            geojson["features"].append(feature)

        serializer = RouteStopSerializer(data=geojson)
        if serializer.is_valid():
            return Response(serializer.data)
        else:
            return Response(
                serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AgencyViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to transit agencies with filtering by agency identifier or name."""

    queryset = Agency.objects.all()
    serializer_class = AgencySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["agency_id", "agency_name"]
    # permission_classes = [permissions.IsAuthenticated]


class StopViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to stops with filtering by identifier, code, name, coordinates, or URL."""

    queryset = Stop.objects.all()
    serializer_class = StopSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "stop_id",
        "stop_code",
        "stop_name",
        "stop_lat",
        "stop_lon",
        "stop_url",
    ]
    # permission_classes = [permissions.IsAuthenticated]


class GeoStopViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide GeoJSON CRUD representations of stops filterable by identifier, location type, zone, parent station, or accessibility."""

    throttle_scope = "geometry"
    queryset = Stop.objects.all()
    serializer_class = GeoStopSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "stop_id",
        "location_type",
        "zone_id",
        "parent_station",
        "wheelchair_boarding",
    ]
    # permission_classes = [permissions.IsAuthenticated]


class RouteViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to routes with filtering by route type or identifier."""

    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["route_type", "route_id"]

    # def get_queryset(self):
    #    queryset = Route.objects.all()
    #    route_id = self.request.query_params.get("route_id")
    #    if route_id is not None:
    #        queryset = queryset.filter(route_id=route_id)
    #    return queryset

    # permission_classes = [permissions.IsAuthenticated]


class CalendarViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to service calendars filterable by service identifier."""

    queryset = Calendar.objects.all()
    serializer_class = CalendarSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["service_id"]
    # permission_classes = [permissions.IsAuthenticated]


class CalendarDateViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to service-date exceptions filterable by service identifier."""

    queryset = CalendarDate.objects.all()
    serializer_class = CalendarDateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["service_id"]
    # permission_classes = [permissions.IsAuthenticated]


class ShapeViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to scheduled shape points filterable by shape identifier."""

    throttle_scope = "geometry"
    queryset = Shape.objects.all()
    serializer_class = ShapeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id"]
    # permission_classes = [permissions.IsAuthenticated]


class GeoShapeViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide GeoJSON CRUD representations of route shapes filterable by shape identifier."""

    throttle_scope = "geometry"
    queryset = GeoShape.objects.all()
    serializer_class = GeoShapeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id"]
    # permission_classes = [permissions.IsAuthenticated]


class TripViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to trips with filtering by shape, direction, trip, route, or service identifiers."""

    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]

    # allowed_query_parameters =  ['shape_id', 'direction_id', 'trip_id', 'route_id', 'service_id']

    # def get_queryset(self):
    #    return self.get_filtered_queryset(self.allowed_query_parameters)

    # permission_classes = [permissions.IsAuthenticated]


class StopTimeViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to scheduled stop times filterable by trip or stop identifier."""

    throttle_scope = "geometry"
    queryset = StopTime.objects.all()
    serializer_class = StopTimeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["trip_id", "stop_id"]
    # permission_classes = [permissions.IsAuthenticated]


class FeedInfoViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to feed metadata filterable by publisher name."""

    queryset = FeedInfo.objects.all()
    serializer_class = FeedInfoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["feed_publisher_name"]
    # permission_classes = [permissions.IsAuthenticated]


class FareAttributeViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to fare attributes."""

    queryset = FareAttribute.objects.all()
    serializer_class = FareAttributeSerializer
    filter_backends = [DjangoFilterBackend]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class FareRuleViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to fare rules, filterable by route identifier."""

    queryset = FareRule.objects.all()
    serializer_class = FareRuleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["route_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class ServiceAlertViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to service alerts with filtering by alert, route, trip, start time, or service date."""

    queryset = Alert.objects.all()
    serializer_class = ServiceAlertSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "alert_id",
        "route_id",
        "trip_id",
        "service_start_time",
        "service_date",
    ]
    # permission_classes = [permissions.IsAuthenticated]


class FeedMessageViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to feed messages."""

    queryset = FeedMessage.objects.all()
    serializer_class = FeedMessageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class TripUpdateViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to trip updates filterable by trip descriptor fields or vehicle identifier."""

    queryset = TripUpdate.objects.all()
    serializer_class = TripUpdateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "trip_trip_id",
        "trip_route_id",
        "trip_start_time",
        "vehicle_id",
    ]
    # permission_classes = [permissions.IsAuthenticated]


class StopTimeUpdateViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to stop-time updates."""

    queryset = StopTimeUpdate.objects.all()
    serializer_class = StopTimeUpdateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]

    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class VehiclePositionViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to vehicle positions with filtering by vehicle and trip descriptor fields."""

    queryset = VehiclePosition.objects.all()
    serializer_class = VehiclePositionSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "vehicle_vehicle_id",
        "vehicle_trip_route_id",
        "vehicle_trip_trip_id",
        "vehicle_trip_schedule_relationship",
    ]

    # permission_classes = [permissions.IsAuthenticated]


class InfoServiceViewSet(viewsets.ReadOnlyModelViewSet):
    """Provide CRUD access to connected information services ordered by creation time and filterable by type or name."""

    queryset = InfoService.objects.all().order_by("created_at")
    serializer_class = InfoServiceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["type", "name"]
    # permission_classes = [permissions.IsAuthenticated]


@require_GET
def get_schema(request: HttpRequest) -> FileResponse:
    """Return the bundled API schema YAML file as a downloadable attachment."""
    file_path = settings.BASE_DIR / "api" / "infobus.yml"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="infobus.yml"
    )


def str_to_timedelta(time_str: str) -> timedelta:
    """Convert a colon-separated hour, minute, and second string into a timedelta."""
    hours, minutes, seconds = map(int, time_str.split(":"))
    duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    return duration
