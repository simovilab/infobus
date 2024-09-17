from django.conf import settings
from django.http import FileResponse
from feed.models import InfoService
from gtfs.models import (
    GTFSProvider,
    Route,
    Trip,
    FeedMessage,
    TripUpdate,
    StopTimeUpdate,
)
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from shapely import geometry
from datetime import datetime, timedelta

from .serializers import *

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
        # TODO: check for errors and exceptions and validations when data is not found

        # Get query parameters
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
        else:
            timestamp = datetime.now()
        next_arrivals = []

        # For trips in progress
        latest_trip_update = FeedMessage.objects.filter(
            entity_type="trip_update"
        ).latest("timestamp")
        # TODO: check TTL (time to live)
        stop_time_updates = StopTimeUpdate.objects.filter(
            feed_message=latest_trip_update, stop_id=stop_id
        )
        current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")

        for stop_time_update in stop_time_updates:
            trip_update = TripUpdate.objects.get(
                id=stop_time_update.trip_update.id,
            )
            trip = Trip.objects.filter(
                trip_id=trip_update.trip_trip_id, feed=current_feed
            ).first()
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

            # For upcoming trips

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
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class FareRuleViewSet(viewsets.ModelViewSet):
    """
    Reglas de tarifa de transporte público.
    """

    queryset = FareRule.objects.all()
    serializer_class = FareRuleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


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

    queryset = FeedMessage.objects.all()
    serializer_class = FeedMessageSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


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
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]

    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


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


class RecordViewSet(viewsets.ModelViewSet):
    """
    Registros de datos.
    """

    queryset = Record.objects.all()
    serializer_class = RecordSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id", "direction_id", "trip_id", "route_id", "service_id"]

    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


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
