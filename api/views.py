from django.conf import settings
from django.http import FileResponse
from feed.models import InfoService
from gtfs.models import (
    GTFSProvider,
    Route,
    RouteStop,
    Trip,
    FeedMessage,
    TripUpdate,
    StopTime,
    StopTimeUpdate,
)
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from shapely import geometry
from datetime import datetime, timedelta
import pytz
from django.conf import settings

from .serializers import *
from django.utils import timezone as dj_timezone
from storage.factory import get_schedule_repository
from gtfs.models import Feed, Stop
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
import requests
import redis

# from .serializers import InfoServiceSerializer, GTFSProviderSerializer, RouteSerializer, TripSerializer


class FilterMixin:
    def get_filtered_queryset(self, allowed_query_params):
        queryset = self.queryset
        query_params = self.request.query_params
        filter_args = {
            param: value
            for param, value in query_params.items()
            if param in allowed_query_params and value is not None
        }
        return queryset.filter(**filter_args)


class ScheduleDeparturesView(APIView):
    """Simple endpoint backed by the DAL to get next scheduled departures at a stop."""

    @extend_schema(
        parameters=[
            OpenApiParameter(name="stop_id", type=OpenApiTypes.STR, required=True, description="Stop identifier (must exist in Stop for the chosen feed)"),
            OpenApiParameter(name="feed_id", type=OpenApiTypes.STR, required=False, description="Feed identifier (defaults to current feed)") ,
            OpenApiParameter(name="date", type=OpenApiTypes.DATE, required=False, description="Service date (YYYY-MM-DD, defaults to today)"),
            OpenApiParameter(name="time", type=OpenApiTypes.STR, required=False, description="Start time (HH:MM or HH:MM:SS, defaults to now)"),
            OpenApiParameter(name="limit", type=OpenApiTypes.INT, required=False, description="Number of results (default 10, max 100)"),
        ],
        responses={200: DalDeparturesResponseSerializer},
        description="Return next scheduled departures at a stop using the DAL (PostgreSQL + Redis cache).",
        tags=["schedule"],
    )
    def get(self, request):
        stop_id = request.query_params.get("stop_id")
        if not stop_id:
            return Response({"error": "stop_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve feed_id
        feed_id = request.query_params.get("feed_id")
        if not feed_id:
            try:
                current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")
            except Feed.DoesNotExist:
                return Response(
                    {"error": "No GTFS feed configured as current (is_current=True). Load GTFS fixtures or import a feed and set one as current."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            feed_id = current_feed.feed_id
        else:
            if not Feed.objects.filter(feed_id=feed_id).exists():
                return Response(
                    {"error": f"feed_id '{feed_id}' not found"}, status=status.HTTP_404_NOT_FOUND
                )

        # Validate stop exists for the chosen feed
        if not Stop.objects.filter(feed__feed_id=feed_id, stop_id=stop_id).exists():
            return Response(
                {"error": f"stop_id '{stop_id}' not found for feed '{feed_id}'"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Parse date/time with TZ defaults
        try:
            date_str = request.query_params.get("date")
            if date_str:
                service_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            else:
                service_date = dj_timezone.localdate()
        except Exception:
            return Response({"error": "Invalid date format. Use YYYY-MM-DD"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            time_str = request.query_params.get("time")
            if time_str:
                fmt = "%H:%M:%S" if len(time_str.split(":")) == 3 else "%H:%M"
                from_time = datetime.strptime(time_str, fmt).time()
            else:
                from_time = dj_timezone.localtime().time()
        except Exception:
            return Response({"error": "Invalid time format. Use HH:MM or HH:MM:SS"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            limit = int(request.query_params.get("limit", 10))
            if limit <= 0 or limit > 100:
                return Response({"error": "limit must be between 1 and 100"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({"error": "limit must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        # Build response using DAL
        repo = get_schedule_repository(use_cache=True)
        departures = repo.get_next_departures(
            feed_id=feed_id,
            stop_id=stop_id,
            service_date=service_date,
            from_time=from_time,
            limit=limit,
        )

        # Format from_time as HH:MM:SS for a cleaner API response
        from_time_str = from_time.strftime("%H:%M:%S")

        payload = {
            "feed_id": feed_id,
            "stop_id": stop_id,
            "service_date": service_date,
            "from_time": from_time_str,
            "limit": limit,
            "departures": departures,
        }
        serializer = DalDeparturesResponseSerializer(payload)
        return Response(serializer.data)


class ArrivalsView(APIView):
    """Arrivals/ETAs endpoint integrating with external Project 4 service if configured.

    Query params:
    - stop_id: required
    - limit: optional, default 10 (1..100)
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(name="stop_id", type=OpenApiTypes.STR, required=True, description="Stop identifier"),
            OpenApiParameter(name="limit", type=OpenApiTypes.INT, required=False, description="Max results (default 10, max 100)"),
        ],
        responses={200: NextTripSerializer},
        description="Return upcoming arrivals (ETAs). If ETAS_API_URL is configured, results are fetched from Project 4; otherwise a 501 is returned.",
        tags=["realtime", "etas"],
    )
    def get(self, request):
        stop_id = request.query_params.get("stop_id")
        if not stop_id:
            return Response({"error": "stop_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            limit = int(request.query_params.get("limit", 10))
            if limit <= 0 or limit > 100:
                return Response({"error": "limit must be between 1 and 100"}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError:
            return Response({"error": "limit must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

        if not getattr(settings, "ETAS_API_URL", None):
            return Response(
                {"error": "ETAs service not configured", "hint": "Set ETAS_API_URL in environment to integrate with Project 4."},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        try:
            resp = requests.get(
                settings.ETAS_API_URL,
                params={"stop_id": stop_id, "limit": limit},
                timeout=5,
            )
            if resp.status_code != 200:
                return Response(
                    {"error": "Failed to fetch ETAs from upstream", "status_code": resp.status_code},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            arrivals = resp.json()
            if not isinstance(arrivals, list):
                # Some services may wrap as {results: []}
                arrivals = arrivals.get("results", []) if isinstance(arrivals, dict) else []
        except Exception as e:
            return Response({"error": f"Upstream ETAs call failed: {e}"}, status=status.HTTP_502_BAD_GATEWAY)

        payload = {
            "stop_id": stop_id,
            "timestamp": dj_timezone.now(),
            "next_arrivals": arrivals,
        }
        serializer = NextTripSerializer(payload)
        return Response(serializer.data)


class StatusView(APIView):
    """Simple health/status endpoint for core dependencies."""

    @extend_schema(
        responses={200: None},
        description="Service status for core dependencies (database, Redis, Fuseki).",
        tags=["status"],
    )
    def get(self, request):
        checks = {
            "database_ok": False,
            "redis_ok": False,
            "fuseki_ok": False,
        }

        # Database check
        try:
            _ = Feed.objects.exists()
            checks["database_ok"] = True
        except Exception:
            checks["database_ok"] = False

        # Redis check
        try:
            r = redis.Redis(host=settings.REDIS_HOST, port=int(settings.REDIS_PORT), db=0, socket_timeout=2)
            checks["redis_ok"] = bool(r.ping())
        except Exception:
            checks["redis_ok"] = False

        # Fuseki check
        try:
            if getattr(settings, "FUSEKI_ENABLED", False) and getattr(settings, "FUSEKI_ENDPOINT", None):
                r = requests.post(
                    settings.FUSEKI_ENDPOINT,
                    data=b"ASK {}",
                    headers={"Content-Type": "application/sparql-query"},
                    timeout=3,
                )
                checks["fuseki_ok"] = (r.status_code == 200)
            else:
                checks["fuseki_ok"] = False
        except Exception:
            checks["fuseki_ok"] = False

        current_feed_id = None
        try:
            current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")
            current_feed_id = current_feed.feed_id
        except Exception:
            current_feed_id = None

        overall = "ok" if all(checks.values()) else ("degraded" if checks["database_ok"] else "error")

        return Response(
            {
                "status": overall,
                **checks,
                "current_feed_id": current_feed_id,
                "time": dj_timezone.now(),
            }
        )


class GTFSProviderViewSet(viewsets.ModelViewSet):
    """
    Proveedores de datos GTFS.
    """

    queryset = GTFSProvider.objects.all()
    serializer_class = GTFSProviderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["code", "name"]
    # permission_classes = [permissions.IsAuthenticated]


class NextTripView(APIView):
    def get(self, request):
        timezone = pytz.timezone(settings.TIME_ZONE)

        # Query parameters
        if request.query_params.get("stop_id"):
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
        else:
            return Response(
                {
                    "error": "Es necesario especificar el stop_id como parámetro de la solicitud: /next-trips?stop_id=bUCR-0-01, por ejemplo."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if request.query_params.get("timestamp"):
            timestamp = request.query_params.get("timestamp")
            timestamp = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S")
            timestamp = timezone.localize(timestamp)
        else:
            timestamp = datetime.now()
            timestamp = timezone.localize(timestamp)

        # Get the current GTFS feed
        current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")
        service_id = get_calendar(timestamp.date(), current_feed)
        if service_id is None:
            return Response(
                {"error": "No hay servicio disponible para la fecha especificada."},
                status=status.HTTP_204_NO_CONTENT,
            )

        next_arrivals = []

        # -----------------
        # Trips in progress
        # -----------------

        latest_feed_message = (
            FeedMessage.objects.filter(entity_type="trip_update")
            .order_by("-timestamp")
            .first()
        )
        # TODO: check TTL (time to live)
        if latest_feed_message is None:
            # No realtime messages available; keep trips_in_progress empty
            stop_time_updates = StopTimeUpdate.objects.none()
        else:
            stop_time_updates = StopTimeUpdate.objects.filter(
                feed_message=latest_feed_message, stop_id=stop_id
            )
        print("Checkpoint 1")

        trips_in_progress = []

        # Build the response for trips in progress
        for stop_time_update in stop_time_updates:
            trip_update = TripUpdate.objects.get(
                id=stop_time_update.trip_update.id,
            )
            trip = Trip.objects.filter(
                trip_id=trip_update.trip_trip_id, feed=current_feed
            ).first()
            trips_in_progress.append(trip)
            route = Route.objects.filter(
                route_id=trip.route_id, feed=current_feed
            ).first()
            vehicle_position = VehiclePosition.objects.filter(
                # TODO: ponder if making a new table for TripDescriptor is better
                vehicle_trip_trip_id=trip_update.trip_trip_id,
                vehicle_trip_start_date=trip_update.trip_start_date,
                vehicle_trip_start_time=trip_update.trip_start_time,
            ).first()
            geo_shape = GeoShape.objects.filter(
                shape_id=trip.shape_id, feed=current_feed
            ).first()
            geo_shape = geometry.LineString(geo_shape.geometry.coords)
            location = vehicle_position.vehicle_position_point
            location = geometry.Point(location.x, location.y)
            position_in_shape = geo_shape.project(location) / geo_shape.length

            next_arrivals.append(
                {
                    "trip_id": trip.trip_id,
                    "route_id": route.route_id,
                    "route_short_name": route.route_short_name,
                    "route_long_name": route.route_long_name,
                    "trip_headsign": trip.trip_headsign,
                    "wheelchair_accessible": trip.wheelchair_accessible,
                    "arrival_time": stop_time_update.arrival_time,
                    "departure_time": stop_time_update.departure_time,
                    "in_progress": True,
                    "progression": {
                        "position_in_shape": position_in_shape,
                        "current_stop_sequence": vehicle_position.vehicle_current_stop_sequence,
                        "current_status": vehicle_position.vehicle_current_status,
                        "occupancy_status": vehicle_position.vehicle_occupancy_status,
                    },
                }
            )

        print(trips_in_progress)

        # ---------------
        # Scheduled trips
        # ---------------

        stop_times = StopTime.objects.filter(
            feed=current_feed,
            stop_id=stop_id,
            arrival_time__gte=timestamp.time(),
            # _trip__service_id=service_id,
        ).order_by("arrival_time")

        print(
            f"Checkpoint 2: {stop_times} {stop_id} {current_feed} {service_id} {timestamp.time()}"
        )

        # Build the response for scheduled trips
        for stop_time in stop_times:
            trip = Trip.objects.filter(
                trip_id=stop_time.trip_id, feed=current_feed
            ).first()
            if trip in trips_in_progress:
                continue
            route = Route.objects.filter(
                route_id=trip.route_id, feed=current_feed
            ).first()

            arrival_time = timezone.localize(
                datetime.combine(timestamp.today(), stop_time.arrival_time)
            )
            departure_time = timezone.localize(
                datetime.combine(timestamp.today(), stop_time.departure_time)
            )

            next_arrivals.append(
                {
                    "trip_id": trip.trip_id,
                    "route_id": route.route_id,
                    "route_short_name": route.route_short_name,
                    "route_long_name": route.route_long_name,
                    "trip_headsign": trip.trip_headsign,
                    "wheelchair_accessible": trip.wheelchair_accessible,
                    "arrival_time": arrival_time,
                    "departure_time": departure_time,
                    "in_progress": False,
                    "progression": None,
                }
            )

        # Sort the list by arrival time
        next_arrivals.sort(key=lambda x: x["arrival_time"])

        data = {
            "stop_id": stop_id,
            "timestamp": timestamp,
            "next_arrivals": next_arrivals,
        }

        serializer = NextTripSerializer(data)
        return Response(serializer.data)


class NextStopView(APIView):
    def get(self, request):
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
            # The serializer needs the timedelta object
            "start_time": str_to_timedelta(start_time),
            "next_stop_sequence": next_stop_sequence,
        }

        print(data)
        serializer = NextStopSerializer(data)

        return Response(serializer.data)


class RouteStopView(APIView):
    def get(self, request):
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


class AgencyViewSet(viewsets.ModelViewSet):
    """
    Agencias de transporte público.
    """

    queryset = Agency.objects.all()
    serializer_class = AgencySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["agency_id", "agency_name"]
    # permission_classes = [permissions.IsAuthenticated]


class StopViewSet(viewsets.ModelViewSet):
    """
    Paradas de transporte público.
    """

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


class GeoStopViewSet(viewsets.ModelViewSet):
    """
    Paradas como GeoJSON.
    """

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


class RouteViewSet(viewsets.ModelViewSet):
    """
    Rutas de transporte público.
    """

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


class CalendarViewSet(viewsets.ModelViewSet):
    """
    Calendarios de transporte público.
    """

    queryset = Calendar.objects.all()
    serializer_class = CalendarSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["service_id"]
    # permission_classes = [permissions.IsAuthenticated]


class CalendarDateViewSet(viewsets.ModelViewSet):
    """
    Fechas de calendario de transporte público.
    """

    queryset = CalendarDate.objects.all()
    serializer_class = CalendarDateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["service_id"]
    # permission_classes = [permissions.IsAuthenticated]


class ShapeViewSet(viewsets.ModelViewSet):
    """
    Formas de transporte público.
    """

    queryset = Shape.objects.all()
    serializer_class = ShapeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id"]
    # permission_classes = [permissions.IsAuthenticated]


class GeoShapeViewSet(viewsets.ModelViewSet):
    """
    Formas geográficas de transporte público.
    """

    queryset = GeoShape.objects.all()
    serializer_class = GeoShapeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id"]
    # permission_classes = [permissions.IsAuthenticated]


class TripViewSet(viewsets.ModelViewSet):
    """
    Viajes de transporte público.
    """

    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]

    # allowed_query_parameters =  ['shape_id', 'direction_id', 'trip_id', 'route_id', 'service_id']

    # def get_queryset(self):
    #    return self.get_filtered_queryset(self.allowed_query_parameters)

    # permission_classes = [permissions.IsAuthenticated]


class StopTimeViewSet(viewsets.ModelViewSet):
    """
    Horarios de paradas de transporte público.
    """

    queryset = StopTime.objects.all()
    serializer_class = StopTimeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["trip_id", "stop_id"]
    # permission_classes = [permissions.IsAuthenticated]


class FeedInfoViewSet(viewsets.ModelViewSet):
    """
    Información de alimentación de transporte público.
    """

    queryset = FeedInfo.objects.all()
    serializer_class = FeedInfoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["feed_publisher_name"]
    # permission_classes = [permissions.IsAuthenticated]


class FareAttributeViewSet(viewsets.ModelViewSet):
    """
    Atributos de tarifa de transporte público.
    """

    queryset = FareAttribute.objects.all()
    serializer_class = FareAttributeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "fare_id",
        "agency_id",
        "currency_type",
        "payment_method",
        "transfers",
    ]
    # permission_classes = [permissions.IsAuthenticated]


class FareRuleViewSet(viewsets.ModelViewSet):
    """
    Reglas de tarifa de transporte público.
    """

    queryset = FareRule.objects.all()
    serializer_class = FareRuleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "fare_id",
        "route_id",
        "origin_id",
        "destination_id",
        "contains_id",
    ]
    # permission_classes = [permissions.IsAuthenticated]


class ServiceAlertViewSet(viewsets.ModelViewSet):
    """
    Alertas de servicio de transporte público.
    """

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


class WeatherViewSet(viewsets.ModelViewSet):
    """
    Condiciones climáticas.
    """

    queryset = Weather.objects.all()
    serializer_class = WeatherSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["weather_location", "weather_condition"]
    # permission_classes = [permissions.IsAuthenticated]


class SocialViewSet(viewsets.ModelViewSet):
    """
    Publicaciones en redes sociales.
    """

    queryset = Social.objects.all()
    serializer_class = SocialSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["social_media", "social_content", "social_location"]
    # permission_classes = [permissions.IsAuthenticated]


class FeedMessageViewSet(viewsets.ModelViewSet):
    """
    Mensajes de alimentación.
    """

    queryset = FeedMessage.objects.all().order_by("-timestamp")
    serializer_class = FeedMessageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "entity_type",
        "provider",
    ]
    # permission_classes = [permissions.IsAuthenticated]


class TripUpdateViewSet(viewsets.ModelViewSet):
    """
    Actualizaciones de viaje.
    """

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


class StopTimeUpdateViewSet(viewsets.ModelViewSet):
    """
    Actualizaciones de horario de parada.
    """

    queryset = StopTimeUpdate.objects.all()
    serializer_class = StopTimeUpdateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "stop_id",
        "stop_sequence",
        "arrival_time",
        "departure_time",
        "schedule_relationship",
        "feed_message",
        "trip_update",
    ]

    # permission_classes = [permissions.IsAuthenticated]


class VehiclePositionViewSet(viewsets.ModelViewSet):
    """
    Posiciones de vehículos.
    """

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


class InfoServiceViewSet(viewsets.ModelViewSet):
    """
    Aplicaciones conectadas al servidor de datos.
    """

    queryset = InfoService.objects.all().order_by("created_at")
    serializer_class = InfoServiceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["type", "name"]
    # permission_classes = [permissions.IsAuthenticated]


def get_schema(request):
    file_path = settings.BASE_DIR / "api" / "datahub.yml"
    return FileResponse(
        open(file_path, "rb"), as_attachment=True, filename="datahub.yml"
    )


def str_to_timedelta(time_str):
    hours, minutes, seconds = map(int, time_str.split(":"))
    duration = timedelta(hours=hours, minutes=minutes, seconds=seconds)
    return duration


def get_calendar(date, current_feed):
    """Get the service_id for the specified date."""
    exception_type = 1  # Service has been added for the specified date.
    exception = CalendarDate.objects.filter(
        feed=current_feed, date=date, exception_type=exception_type
    ).first()

    if exception:
        service_id = exception.service_id
    else:
        day_of_week = date.strftime("%A").lower()
        kwargs = {"feed": current_feed, day_of_week: True}
        calendar = Calendar.objects.filter(**kwargs).first()
        if not calendar:
            service_id = None
        else:
            service_id = calendar.service_id

    return service_id
