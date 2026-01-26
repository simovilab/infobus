from django.conf import settings
from django.http import FileResponse
from feed.models import InfoService
from gtfs.models import (
    GTFSProvider,
    Feed,
    Route,
    RouteStop,
    Trip,
    FeedMessage,
    TripUpdate,
    StopTime,
    StopTimeUpdate,
)
from rest_framework import viewsets, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.filters import OrderingFilter
from rest_framework.exceptions import ValidationError
from django.db.models import Max, Min, OuterRef, Subquery
from django.db.models.functions import Coalesce
from shapely import geometry
from datetime import datetime, timedelta
import re
import pytz
from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.measure import D
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.db.models import Q

from drf_spectacular.utils import OpenApiExample, extend_schema

from .serializers import *
from .models import UserData, UserReport, WideAlert
from .permissions import ApiKeyAuthentication

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


class LimitOffsetArrayResponseMixin:
    """Manual queryset slicing to ensure an array response (OpenAPI compliance) instead of the DRF pagination object.
    Supports limit [1,max_limit] and offset ≥0; defaults to the full list if parameters are missing."""

    default_limit = 100
    max_limit = 1000

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        has_limit = "limit" in request.query_params
        has_offset = "offset" in request.query_params
        if not has_limit and not has_offset:
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)

        # Use defaults only when the client opts into limit/offset.
        # This keeps the legacy behavior (full list) when no pagination params are present.
        limit_raw = request.query_params.get("limit", self.default_limit)
        offset_raw = request.query_params.get("offset", 0)

        try:
            limit = int(limit_raw)
            offset = int(offset_raw)
        except ValueError:
            raise ValidationError({"limit": "Debe ser entero.", "offset": "Debe ser entero."})

        if limit < 1 or limit > self.max_limit:
            raise ValidationError({"limit": f"Debe estar entre 1 y {self.max_limit}."})
        if offset < 0:
            raise ValidationError({"offset": "Debe ser >= 0."})

        queryset = queryset[offset : offset + limit]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class CurrentFeedQuerysetMixin:
    """Filter GTFS Schedule tables to the current feed (is_current).
    Returns an empty list if none."""

    def get_current_feed(self):
        if hasattr(self.request, "_current_feed"):
            return self.request._current_feed

        try:
            feed = Feed.objects.filter(is_current=True).latest("retrieved_at")
        except Feed.DoesNotExist:
            feed = None

        self.request._current_feed = feed
        return feed

    def get_queryset(self):
        queryset = super().get_queryset()
        feed = self.get_current_feed()
        if feed is None:
            return queryset.none()
        if hasattr(queryset.model, "feed"):
            return queryset.filter(feed=feed)
        return queryset


def _get_latest_realtime_feed_message(entity_type: str):
    """Return the latest FeedMessage for `entity_type` if it is fresh enough.

    Freshness is controlled by settings.DATAHUB_REALTIME_TTL_SECONDS.
    If TTL is <= 0, freshness checks are effectively disabled.
    """

    latest = FeedMessage.objects.filter(entity_type=entity_type).order_by("-timestamp").first()
    if latest is None:
        return None

    ttl_seconds = getattr(settings, "DATAHUB_REALTIME_TTL_SECONDS", 300)
    try:
        ttl_seconds = int(ttl_seconds)
    except (TypeError, ValueError):
        ttl_seconds = 300

    if ttl_seconds > 0:
        cutoff = timezone.now() - timedelta(seconds=ttl_seconds)
        if latest.timestamp and latest.timestamp < cutoff:
            return None

    return latest


class ErrorEnvelopeMixin:
    """Return OpenAPI `Error` objects instead of DRF's default error shapes.

    The contract defines error responses as:
    `{ "code": <int>, "message": <string> }`
    """

    def _error(self, status_code: int, message: str):
        return Response({"code": int(status_code), "message": str(message)}, status=status_code)

    def _detail_to_message(self, status_code: int, detail):
        defaults = {
            400: "Solicitud inválida",
            401: "No autorizado",
            403: "Prohibido",
            404: "No encontrado",
            429: "Demasiadas solicitudes",
            500: "Error interno",
        }

        if status_code in defaults:
            return defaults[status_code]

        if detail is None:
            return "Error"

        # DRF can return strings, lists or dicts for `detail`.
        if isinstance(detail, str):
            return detail
        if isinstance(detail, list) and detail:
            return str(detail[0])
        if isinstance(detail, dict) and detail:
            # Prefer the first field's first error message.
            first_value = next(iter(detail.values()))
            if isinstance(first_value, list) and first_value:
                return str(first_value[0])
            return str(first_value)

        return "Error"

    def handle_exception(self, exc):
        # Convert DRF APIExceptions (ValidationError, ParseError, NotFound, etc.)
        # into the OpenAPI `Error` envelope.
        try:
            from rest_framework.exceptions import APIException

            if isinstance(exc, APIException):
                status_code = int(getattr(exc, "status_code", 500) or 500)
                detail = getattr(exc, "detail", None)
                return self._error(status_code, self._detail_to_message(status_code, detail))
        except Exception:
            # Silently fall through to default DRF exception handling if conversion fails
            pass

        return super().handle_exception(exc)


class GTFSProviderViewSet(ErrorEnvelopeMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Proveedores de datos GTFS.
    """

    queryset = GTFSProvider.objects.all()
    serializer_class = GTFSProviderSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["code", "name"]
    # permission_classes = [permissions.IsAuthenticated]


class NextTripView(generics.GenericAPIView):
    serializer_class = NextTripSerializer

    @extend_schema(responses=NextTripSerializer)
    def get(self, request):
        timezone = pytz.timezone(settings.TIME_ZONE)

        # Query parameters
        stop_id = request.query_params.get("stop_id")
        if not stop_id:
            return Response(
                {
                    "code": 400,
                    "message": "Es necesario especificar el stop_id como parámetro de la solicitud: /next-trips?stop_id=bUCR-0-01, por ejemplo."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        timestamp_raw = request.query_params.get("timestamp")
        if timestamp_raw:
            try:
                # Try parsing as ISO 8601 with timezone first
                from django.utils.dateparse import parse_datetime
                timestamp = parse_datetime(timestamp_raw)
                if timestamp is None:
                    # Fallback to naive datetime parsing
                    timestamp = datetime.strptime(timestamp_raw, "%Y-%m-%dT%H:%M:%S")
                    timestamp = timezone.localize(timestamp)
                elif timezone.is_naive(timestamp):
                    # Make timezone-aware if parsed as naive
                    timestamp = timezone.localize(timestamp)
            except (ValueError, TypeError):
                return Response(
                    {"code": 400, "message": "timestamp inválido. Use formato ISO 8601 (ej. 2024-07-31T16:12:25 o 2024-07-31T16:12:25-06:00)"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            timestamp = datetime.now()
            timestamp = timezone.localize(timestamp)

        # Get the current GTFS feed
        try:
            current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")
        except Feed.DoesNotExist:
            serializer = self.get_serializer(
                data={"stop_id": stop_id, "timestamp": timestamp, "next_arrivals": []}
            )
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)

        # Validate stop exists in the current feed
        if not Stop.objects.filter(feed=current_feed, stop_id=stop_id).exists():
            return Response(
                {"code": 404, "message": f"No existe la parada especificada {stop_id} en la base de datos."},
                status=status.HTTP_404_NOT_FOUND,
            )

        service_id = get_calendar(timestamp.date(), current_feed)
        if service_id is None:
            serializer = self.get_serializer(
                data={"stop_id": stop_id, "timestamp": timestamp, "next_arrivals": []}
            )
            serializer.is_valid(raise_exception=True)
            return Response(serializer.data)

        next_arrivals = []

        # -----------------
        # Trips in progress
        # -----------------

        latest_feed_message = _get_latest_realtime_feed_message("trip_update")
        if latest_feed_message is None:
            stop_time_updates = StopTimeUpdate.objects.none()
        else:
            stop_time_updates = (
                StopTimeUpdate.objects.filter(feed_message=latest_feed_message, stop_id=stop_id)
                .select_related("trip_update")
                .order_by("stop_sequence")
            )

        trips_in_progress_ids = set()

        realtime_trip_ids = [
            stu.trip_update.trip_trip_id
            for stu in stop_time_updates
            if getattr(stu.trip_update, "trip_trip_id", None)
        ]
        trips_by_id = {
            t.trip_id: t
            for t in Trip.objects.filter(feed=current_feed, trip_id__in=realtime_trip_ids)
        }

        route_ids = [t.route_id for t in trips_by_id.values() if getattr(t, "route_id", None)]
        routes_by_id = {
            r.route_id: r
            for r in Route.objects.filter(feed=current_feed, route_id__in=route_ids)
        }

        # Build the response for trips in progress
        for stop_time_update in stop_time_updates:
            trip_update = stop_time_update.trip_update
            trip_id = getattr(trip_update, "trip_trip_id", None)
            if not trip_id:
                continue

            trip = trips_by_id.get(trip_id)
            if trip is None:
                continue

            trips_in_progress_ids.add(trip.trip_id)

            route = routes_by_id.get(getattr(trip, "route_id", None))
            if route is None:
                continue

            vehicle_position = VehiclePosition.objects.filter(
                vehicle_trip_trip_id=trip_id,
                vehicle_trip_start_date=trip_update.trip_start_date,
                vehicle_trip_start_time=trip_update.trip_start_time,
            ).first()

            progression = None
            try:
                if vehicle_position and vehicle_position.vehicle_position_point and trip.shape_id:
                    geo_shape = GeoShape.objects.filter(
                        shape_id=trip.shape_id, feed=current_feed
                    ).first()
                    if geo_shape and geo_shape.geometry:
                        shape_line = geometry.LineString(geo_shape.geometry.coords)
                        location = vehicle_position.vehicle_position_point
                        point = geometry.Point(location.x, location.y)
                        if shape_line.length:
                            position_in_shape = shape_line.project(point) / shape_line.length
                        else:
                            position_in_shape = 0.0
                        progression = {
                            "position_in_shape": float(position_in_shape),
                            "current_stop_sequence": vehicle_position.vehicle_current_stop_sequence,
                            "current_status": vehicle_position.vehicle_current_status,
                            "occupancy_status": vehicle_position.vehicle_occupancy_status,
                        }
            except Exception:
                progression = None

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
                    "progression": progression,
                    "source": "GTFS-RT",
                }
            )

        # ---------------
        # Scheduled trips
        # ---------------

        stop_times = StopTime.objects.filter(
            feed=current_feed,
            stop_id=stop_id,
            arrival_time__gte=timestamp.time(),
            # _trip__service_id=service_id,
        ).order_by("arrival_time")

        # Build the response for scheduled trips
        for stop_time in stop_times:
            trip = Trip.objects.filter(
                trip_id=stop_time.trip_id, feed=current_feed
            ).first()
            if not trip:
                continue
            if trip.trip_id in trips_in_progress_ids:
                continue
            route = Route.objects.filter(
                route_id=trip.route_id, feed=current_feed
            ).first()
            if not route:
                continue

            if stop_time.arrival_time is None or stop_time.departure_time is None:
                continue

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
                    "source": "GTFS",
                }
            )

        # Sort the list by arrival time
        next_arrivals.sort(key=lambda x: x.get("arrival_time") or x.get("departure_time") or timestamp)

        data = {
            "stop_id": stop_id,
            "timestamp": timestamp,
            "next_arrivals": next_arrivals,
        }

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class NextStopView(generics.GenericAPIView):
    serializer_class = NextStopSerializer

    @extend_schema(responses=NextStopSerializer)
    def get(self, request):
        # Get query parameters
        trip_id = request.query_params.get("trip_id")
        start_date = request.query_params.get("start_date")
        start_time = request.query_params.get("start_time")

        if not trip_id or not start_date or not start_time:
            return Response(
                {
                    "code": 400,
                    "message": "Es necesario especificar todos los parámetros de la solicitud, trip_id, start_date y start_time."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        next_stop_sequence = []

        # Parse start_date - accept both YYYYMMDD (GTFS format) and YYYY-MM-DD
        start_date_parsed = None
        if start_date:
            # First try standard formats supported by parse_date (e.g., YYYY-MM-DD)
            start_date_parsed = parse_date(start_date)
            # If that fails, try GTFS YYYYMMDD format explicitly
            if start_date_parsed is None and re.fullmatch(r"\d{8}", start_date):
                try:
                    start_date_parsed = datetime.strptime(start_date, "%Y%m%d").date()
                except ValueError:
                    start_date_parsed = None

        if start_date_parsed is None:
            return Response(
                {"code": 400, "message": "start_date inválido. Use formato YYYYMMDD o YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            start_time_td = str_to_timedelta(start_time)
        except Exception:
            return Response(
                {"code": 400, "message": "start_time inválido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # For trips in progress
        latest_trip_update = _get_latest_realtime_feed_message("trip_update")
        try:
            current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")
        except Feed.DoesNotExist:
            current_feed = None

        if latest_trip_update is not None:
            trip_update = TripUpdate.objects.filter(
                feed_message=latest_trip_update,
                trip_trip_id=trip_id,
                trip_start_date=start_date_parsed,
                trip_start_time=start_time_td,
            ).first()
        else:
            trip_update = None

        if trip_update is not None and current_feed is not None:
            stop_time_updates = StopTimeUpdate.objects.filter(trip_update=trip_update).order_by(
                "stop_sequence"
            )
            stop_ids = [u.stop_id for u in stop_time_updates if u.stop_id]
            stops_by_id = {
                s.stop_id: s
                for s in Stop.objects.filter(feed=current_feed, stop_id__in=stop_ids)
            }

            for stop_time_update in stop_time_updates:
                stop = stops_by_id.get(stop_time_update.stop_id)
                if stop is None:
                    continue
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
            "start_date": start_date_parsed,
            "start_time": start_time_td,
            "next_stop_sequence": next_stop_sequence,
        }

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class RouteStopView(generics.GenericAPIView):
    serializer_class = RouteStopsSerializer

    @extend_schema(responses=RouteStopsSerializer(many=True))
    def get(self, request):
        try:
            current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")
        except Feed.DoesNotExist:
            return Response([])

        route_id = request.query_params.get("route_id")
        limit = request.query_params.get("limit", 100)
        offset = request.query_params.get("offset", 0)
        ordering = request.query_params.get("ordering", "stop_sequence")

        try:
            limit = int(limit)
            offset = int(offset)
        except ValueError:
            return Response(
                {"code": 400, "message": "Parámetros inválidos: limit/offset deben ser enteros."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if limit < 1 or limit > 1000 or offset < 0:
            return Response(
                {"code": 400, "message": "Parámetros inválidos: limit debe ser 1..1000 y offset >= 0."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        allowed_ordering = {
            "route_id",
            "stop_sequence",
            "stop_id",
        }
        ordering_field = ordering.lstrip("-")
        if ordering_field not in allowed_ordering:
            return Response(
                {
                    "code": 400,
                    "message": "Parámetro inválido: ordering no permitido."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        route_stops = RouteStop.objects.filter(feed=current_feed)
        if route_id:
            route_stops = route_stops.filter(route_id=route_id)

        route_stops = route_stops.order_by(ordering)[offset : offset + limit]

        stop_ids = [rs.stop_id for rs in route_stops]
        stops_by_id = {
            s.stop_id: s
            for s in Stop.objects.filter(feed=current_feed, stop_id__in=stop_ids)
        }

        items = []
        for rs in route_stops:
            stop = stops_by_id.get(rs.stop_id)
            if stop is None:
                continue

            items.append(
                {
                    "route_id": rs.route_id,
                    "stop_sequence": rs.stop_sequence,
                    "stop_id": stop.stop_id,
                    "stop_name": stop.stop_name,
                    "stop_lat": stop.stop_lat,
                    "stop_lon": stop.stop_lon,
                }
            )

        return Response(items)


class AgencyViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Agencias de transporte público.
    """

    queryset = Agency.objects.all()
    serializer_class = AgencySerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["agency_id", "agency_name"]
    # permission_classes = [permissions.IsAuthenticated]


class StopViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Paradas de transporte público.
    """

    queryset = Stop.objects.all()
    serializer_class = StopSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = [
        "stop_id",
        "stop_name",
        "location_type",
        "wheelchair_boarding",
        "parent_station",
    ]
    # permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()

        current_feed = self.get_current_feed()

        # Optional filter: route_id (via StopTime -> Trip)
        route_id = self.request.query_params.get("route_id")
        if route_id:
            trip_ids = Trip.objects.filter(feed=current_feed, route_id=route_id).values_list(
                "trip_id", flat=True
            )
            stop_ids = StopTime.objects.filter(feed=current_feed, trip_id__in=trip_ids).values_list(
                "stop_id", flat=True
            )
            queryset = queryset.filter(stop_id__in=stop_ids).distinct()

        # Spatial filter: located_within (WKT geometry)
        located_within = self.request.query_params.get("located_within")
        if located_within:
            try:
                geom = GEOSGeometry(located_within)
                if geom.srid is None:
                    geom.srid = 4326
            except Exception:
                raise ValidationError({"located_within": "WKT inválido."})
            queryset = queryset.filter(stop_point__within=geom)

        # Spatial filter: close_to (WKT point) + distance (meters)
        close_to = self.request.query_params.get("close_to")
        if close_to:
            distance_m = self.request.query_params.get("distance", 800)
            try:
                distance_m = int(distance_m)
            except ValueError:
                raise ValidationError({"distance": "Debe ser entero (metros)."})
            try:
                point = GEOSGeometry(close_to)
                if point.srid is None:
                    point.srid = 4326
            except Exception:
                raise ValidationError({"close_to": "WKT inválido. Debe ser POINT (...)"})

            if point.geom_type.upper() != "POINT":
                raise ValidationError({"close_to": "Debe ser un POINT en WKT."})

            if distance_m < 0:
                raise ValidationError({"distance": "Debe ser >= 0."})

            queryset = queryset.filter(stop_point__distance_lte=(point, D(m=distance_m)))

        return queryset


class GeoStopViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Paradas como GeoJSON.
    """

    queryset = Stop.objects.all()
    serializer_class = GeoStopSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = [
        "stop_id",
        "location_type",
        "zone_id",
        "parent_station",
        "wheelchair_boarding",
    ]
    # permission_classes = [permissions.IsAuthenticated]


class RouteViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Rutas de transporte público.
    """

    queryset = Route.objects.all()
    serializer_class = RouteSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["route_type", "route_id"]

    # def get_queryset(self):
    #    queryset = Route.objects.all()
    #    route_id = self.request.query_params.get("route_id")
    #    if route_id is not None:
    #        queryset = queryset.filter(route_id=route_id)
    #    return queryset

    # permission_classes = [permissions.IsAuthenticated]


class CalendarViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Calendarios de transporte público.
    """

    queryset = Calendar.objects.all()
    serializer_class = CalendarSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["service_id"]
    # permission_classes = [permissions.IsAuthenticated]


class CalendarDateViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Fechas de calendario de transporte público.
    """

    queryset = CalendarDate.objects.all()
    serializer_class = CalendarDateSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["service_id"]
    # permission_classes = [permissions.IsAuthenticated]


class ShapeViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Formas de transporte público.
    """

    queryset = Shape.objects.all()
    serializer_class = ShapeSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["shape_id"]
    # permission_classes = [permissions.IsAuthenticated]


class GeoShapeViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Formas geográficas de transporte público.
    """

    queryset = GeoShape.objects.all()
    serializer_class = GeoShapeSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["shape_id"]
    # permission_classes = [permissions.IsAuthenticated]


class TripViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Viajes de transporte público.
    """

    queryset = Trip.objects.all()
    serializer_class = TripSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]

    # allowed_query_parameters =  ['shape_id', 'direction_id', 'trip_id', 'route_id', 'service_id']

    # def get_queryset(self):
    #    return self.get_filtered_queryset(self.allowed_query_parameters)

    # permission_classes = [permissions.IsAuthenticated]


class StopTimeViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Horarios de paradas de transporte público.
    """

    queryset = StopTime.objects.all()
    serializer_class = StopTimeSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["trip_id", "stop_id"]
    # permission_classes = [permissions.IsAuthenticated]


class FeedInfoViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Información de alimentación de transporte público.
    """

    queryset = FeedInfo.objects.all()
    serializer_class = FeedInfoSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["feed_publisher_name"]
    # permission_classes = [permissions.IsAuthenticated]


class TripTimesView(generics.GenericAPIView):
    """Ventana horaria por viaje, derivada de StopTimes."""

    serializer_class = TripTimesSerializer

    default_limit = 100
    max_limit = 1000
    allowed_ordering = {"trip_id", "start_time", "end_time", "duration"}

    @extend_schema(responses=TripTimesSerializer(many=True))
    def get(self, request):
        limit_raw = request.query_params.get("limit", self.default_limit)
        offset_raw = request.query_params.get("offset", 0)

        try:
            limit = int(limit_raw)
            offset = int(offset_raw)
        except ValueError:
            raise ValidationError({"limit": "Debe ser entero.", "offset": "Debe ser entero."})

        if limit < 1 or limit > self.max_limit:
            raise ValidationError({"limit": f"Debe estar entre 1 y {self.max_limit}."})
        if offset < 0:
            raise ValidationError({"offset": "Debe ser >= 0."})

        ordering = request.query_params.get("ordering")
        if ordering:
            ordering_field = ordering[1:] if ordering.startswith("-") else ordering
            if ordering_field not in self.allowed_ordering:
                raise ValidationError(
                    {
                        "ordering": f"Campo inválido. Permitidos: {sorted(self.allowed_ordering)}"
                    }
                )
        else:
            ordering = "trip_id"

        trip_id = request.query_params.get("trip_id")

        try:
            current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")
        except Feed.DoesNotExist:
            return Response([])

        stop_times = StopTime.objects.filter(feed=current_feed)
        if trip_id:
            stop_times = stop_times.filter(trip_id=trip_id)

        base = stop_times.values("trip_id").annotate(
            min_seq=Min("stop_sequence"),
            max_seq=Max("stop_sequence"),
        )

        start_departure_sq = StopTime.objects.filter(
            feed=current_feed,
            trip_id=OuterRef("trip_id"),
            stop_sequence=OuterRef("min_seq"),
        ).values("departure_time")[:1]

        start_arrival_sq = StopTime.objects.filter(
            feed=current_feed,
            trip_id=OuterRef("trip_id"),
            stop_sequence=OuterRef("min_seq"),
        ).values("arrival_time")[:1]

        end_arrival_sq = StopTime.objects.filter(
            feed=current_feed,
            trip_id=OuterRef("trip_id"),
            stop_sequence=OuterRef("max_seq"),
        ).values("arrival_time")[:1]

        end_departure_sq = StopTime.objects.filter(
            feed=current_feed,
            trip_id=OuterRef("trip_id"),
            stop_sequence=OuterRef("max_seq"),
        ).values("departure_time")[:1]

        base = base.annotate(
            start_time=Coalesce(Subquery(start_departure_sq), Subquery(start_arrival_sq)),
            end_time=Coalesce(Subquery(end_arrival_sq), Subquery(end_departure_sq)),
        )

        items = []
        for row in base:
            start_time = row.get("start_time")
            end_time = row.get("end_time")
            if start_time is None or end_time is None:
                continue

            start_seconds = start_time.hour * 3600 + start_time.minute * 60 + start_time.second
            end_seconds = end_time.hour * 3600 + end_time.minute * 60 + end_time.second
            if end_seconds < start_seconds:
                end_seconds += 24 * 3600

            items.append(
                {
                    "trip_id": row["trip_id"],
                    "start_time": start_time.strftime("%H:%M:%S"),
                    "end_time": end_time.strftime("%H:%M:%S"),
                    "duration": int(end_seconds - start_seconds),
                }
            )

        reverse = ordering.startswith("-")
        ordering_field = ordering[1:] if reverse else ordering
        items.sort(key=lambda x: x[ordering_field], reverse=reverse)

        return Response(items[offset : offset + limit])


class FareAttributeViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Atributos de tarifa de transporte público.
    """

    queryset = FareAttribute.objects.all()
    serializer_class = FareAttributeSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["fare_id", "currency_type", "payment_method", "transfers", "agency_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class FareRuleViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Reglas de tarifa de transporte público.
    """

    queryset = FareRule.objects.all()
    serializer_class = FareRuleSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["fare_id", "route_id", "origin_id", "destination_id", "contains_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class ServiceAlertViewSet(ErrorEnvelopeMixin, CurrentFeedQuerysetMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Alertas de servicio de transporte público.
    """

    queryset = Alert.objects.all()
    serializer_class = ServiceAlertPublicSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = [
        "alert_id",
        "route_id",
        "trip_id",
        "service_start_time",
        "service_date",
    ]
    # permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses=ServiceAlertPublicSerializer(many=True),
        examples=[
            OpenApiExample(
                "basic",
                summary="Active service alerts",
                value=[
                    {
                        "alert_id": "bUCR-001",
                        "header_text": "Cierre de vías",
                        "description_text": "Cierre de vías en la Ciudad de la Investigación",
                        "url": "https://bucr.digital/alertas/bUCR-001",
                        "effect": "DETOUR",
                        "cause": "MAINTENANCE",
                        "severity": "MINOR",
                        "lifecycle": "ONGOING",
                        "active_period": [{"start": "2024-07-31T08:00:00-06:00", "end": "2024-07-31T18:00:00-06:00"}],
                        "informed_entity": [{"route_id": "bUCR-L1", "stop_id": "bUCR-0-03"}],
                    }
                ],
            )
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        active = self.request.query_params.get("active")
        if active is None:
            return queryset

        active_bool = str(active).lower() in {"1", "true", "yes"}
        now = timezone.localtime()
        if active_bool:
            return queryset.filter(
                service_date=now.date(),
                service_start_time__lte=now.time(),
                service_end_time__gte=now.time(),
            )
        return queryset


class WeatherViewSet(ErrorEnvelopeMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Condiciones climáticas.
    """

    queryset = Weather.objects.all()
    serializer_class = WeatherPublicSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["weather_location", "weather_condition"]
    # permission_classes = [permissions.IsAuthenticated]


class SocialViewSet(ErrorEnvelopeMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Publicaciones en redes sociales.
    """

    queryset = Social.objects.all()
    serializer_class = SocialPublicSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["social_media", "social_content", "social_location"]
    # permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # The OpenAPI schema requires `url` and `timestamp`. Our current model does not
        # have a dedicated URL field, so we only expose rows where `social_id` already
        # contains a usable URL.
        queryset = super().get_queryset()
        return queryset.filter(
            (Q(social_id__startswith="http://") | Q(social_id__startswith="https://"))
            & Q(social_date__isnull=False)
            & Q(social_time__isnull=False)
        )


class FeedMessageViewSet(viewsets.ModelViewSet):
    """
    Mensajes de alimentación.
    """

    queryset = FeedMessage.objects.all()
    serializer_class = FeedMessageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class TripUpdateViewSet(ErrorEnvelopeMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Actualizaciones de viaje.
    """

    queryset = TripUpdate.objects.select_related("feed_message").prefetch_related("stoptimeupdate_set").all()
    serializer_class = TripUpdatePublicSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = [
        "trip_trip_id",
        "trip_route_id",
        "trip_start_time",
        "vehicle_id",
    ]
    # permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        responses=TripUpdatePublicSerializer(many=True),
        examples=[
            OpenApiExample(
                "basic",
                summary="Trip updates",
                value=[
                    {
                        "trip_id": "JFH367",
                        "route_id": "bUCR-L1",
                        "vehicle_id": "VEH-123",
                        "timestamp": "2024-07-31T07:12:25-06:00",
                        "ttl_seconds": 300,
                        "source": "GTFS-RT",
                        "stop_time_update": [
                            {
                                "stop_id": "bUCR-0-03",
                                "stop_sequence": 15,
                                "arrival": {"time": "2024-07-31T07:15:00-06:00", "delay": 120},
                                "departure": {"time": "2024-07-31T07:16:00-06:00", "delay": 120},
                                "schedule_relationship": "SCHEDULED",
                            }
                        ],
                    }
                ],
            )
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class StopTimeUpdateViewSet(viewsets.ModelViewSet):
    """
    Actualizaciones de horario de parada.
    """

    queryset = StopTimeUpdate.objects.all()
    serializer_class = StopTimeUpdateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]

    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class VehiclePositionViewSet(ErrorEnvelopeMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Posiciones de vehículos.
    """

    queryset = VehiclePosition.objects.select_related("feed_message").all()
    serializer_class = VehiclePositionPublicSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = [
        "vehicle_vehicle_id",
        "vehicle_trip_route_id",
        "vehicle_trip_trip_id",
        "vehicle_trip_schedule_relationship",
    ]

    @extend_schema(
        responses=VehiclePositionPublicSerializer(many=True),
        examples=[
            OpenApiExample(
                "basic",
                summary="Vehicle positions",
                value=[
                    {
                        "vehicle": {
                            "id": "MEYS-8236",
                            "label": "MEYS-8236",
                            "wheelchair_accessible": "WHEELCHAIR_ACCESSIBLE",
                        },
                        "schedule": {
                            "current_stop_sequence": 15,
                            "stop_id": "bUCR-0-03",
                            "current_status": "IN_TRANSIT_TO",
                        },
                        "timestamp": "2024-07-31T07:12:25-06:00",
                        "ttl_seconds": 300,
                    }
                ],
            )
        ],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        queryset = super().get_queryset()
        updated_since = self.request.query_params.get("updated_since")
        if not updated_since:
            return queryset

        try:
            dt = datetime.fromisoformat(updated_since.replace("Z", "+00:00"))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
        except Exception:
            raise ValidationError({"updated_since": "Debe ser date-time ISO 8601."})

        return queryset.filter(vehicle_timestamp__gte=dt)


class InfoServiceViewSet(ErrorEnvelopeMixin, LimitOffsetArrayResponseMixin, viewsets.ReadOnlyModelViewSet):
    """
    Aplicaciones conectadas al servidor de datos.
    """

    queryset = InfoService.objects.all().order_by("created_at")
    serializer_class = InfoServicePublicSerializer
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    ordering_fields = "__all__"
    filterset_fields = ["type", "name"]
    # permission_classes = [permissions.IsAuthenticated]


class WideAlertsView(ErrorEnvelopeMixin, generics.GenericAPIView):
    serializer_class = WideAlertSerializer

    def get_authenticators(self):
        if self.request.method.upper() == "POST":
            return [ApiKeyAuthentication()]
        return []

    @extend_schema(responses=WideAlertSerializer(many=True))
    def get(self, request):
        queryset = WideAlert.objects.all().order_by("-timestamp")
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(request=WideAlertSerializer, responses=WideAlertSerializer)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response(self.serializer_class(obj).data, status=status.HTTP_201_CREATED)


class UserReportsView(ErrorEnvelopeMixin, generics.GenericAPIView):
    def get_authenticators(self):
        # GET is public (responses anonymized).
        # POST requires ApiKeyAuth to prevent spam and ensure trusted submissions
        if self.request.method.upper() == "POST":
            return [ApiKeyAuthentication()]
        return []

    @extend_schema(responses=UserReportSerializer(many=True))
    def get(self, request):
        queryset = UserReport.objects.all().order_by("-timestamp")
        retention_days = getattr(settings, "DATAHUB_USER_REPORTS_RETENTION_DAYS", 30)
        try:
            retention_days = int(retention_days)
        except (TypeError, ValueError):
            retention_days = 30
        if retention_days > 0:
            cutoff = timezone.now() - timedelta(days=retention_days)
            queryset = queryset.filter(timestamp__gte=cutoff)
        serializer = UserReportSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(request=UserReportCreateSerializer, responses=UserReportCreatedSerializer)
    def post(self, request):
        serializer = UserReportCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        location = data["location"]
        evidence = data.get("user_evidence") or []

        stored_evidence = []
        for item in evidence:
            # Public API only exposes URL-based evidence. If a client submits b64,
            # we intentionally do not persist/return it (writeOnly in the OpenAPI contract).
            url = item.get("url")
            if url:
                stored_evidence.append({"type": item["type"], "url": url})

        description = data["description"]
        # Basic PII redaction for common patterns (email/phone) to keep stored data anonymous.
        description = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[redacted]", description)
        description = re.sub(r"\b\+?\d[\d\s().-]{7,}\d\b", "[redacted]", description)

        report = UserReport.objects.create(
            report_type=data["report_type"],
            location_stop_id=location.get("stop_id"),
            location_lat=location.get("lat"),
            location_lon=location.get("lon"),
            description=description,
            user_evidence=stored_evidence,
        )

        # Best-effort retention enforcement on write.
        retention_days = getattr(settings, "DATAHUB_USER_REPORTS_RETENTION_DAYS", 30)
        try:
            retention_days = int(retention_days)
        except (TypeError, ValueError):
            retention_days = 30
        if retention_days > 0:
            cutoff = timezone.now() - timedelta(days=retention_days)
            UserReport.objects.filter(timestamp__lt=cutoff).delete()

        return Response(
            {"report_id": report.report_id, "status": "created"},
            status=status.HTTP_201_CREATED,
        )


class UserDataView(ErrorEnvelopeMixin, generics.GenericAPIView):
    serializer_class = UserDataSerializer

    def get_authenticators(self):
        # POST is protected because it allows writes to a user identifier store.
        # Unauthenticated writes would allow spam and dataset poisoning.
        if self.request.method.upper() == "POST":
            return [ApiKeyAuthentication()]
        return []

    @extend_schema(responses=UserDataSerializer(many=True))
    def get(self, request):
        queryset = UserData.objects.all().order_by("user_id")
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(request=UserDataSerializer, responses=UserDataSerializer)
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        obj, created = UserData.objects.get_or_create(user_id=user_id)
        response_serializer = self.serializer_class(obj)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


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
