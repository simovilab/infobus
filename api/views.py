from django.conf import settings
from django.http import FileResponse
from feed.models import InfoService, InfoProvider
from gtfs.models import (
    GTFSProvider,
    Route,
    RouteStop,
    Trip,
    FeedMessage,
    TripUpdate,
    StopTimeUpdate,
    VehiclePosition,
    Alert,

)
from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from shapely import geometry
from datetime import datetime, timedelta
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

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

    retrieve:
    Obtiene un proveedor de datos GTFS específico.

    list:
    Lista todos los proveedores de datos GTFS.

    create:
    Crea un nuevo proveedor de datos GTFS.

    update:
    Actualiza un proveedor de datos GTFS existente.

    delete:
    Elimina un proveedor de datos GTFS existente.

    partial_update:
    Actualiza parcialmente un proveedor de datos GTFS existente.
    """

    queryset = GTFSProvider.objects.all()
    serializer_class = GTFSProviderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["code", "name"]
    # permission_classes = [permissions.IsAuthenticated]


class NextTripView(APIView):
    """
    Obtiene la siguiente llegada de un viaje a una parada específica.

    get:
    Obtiene la siguiente llegada de un viaje a una parada específica.
    """

    @swagger_auto_schema(
        operation_description="Devuelve la siguiente llegada de un viaje a una parada específica.",
        manual_parameters=[
            openapi.Parameter(
                "stop_id", openapi.IN_QUERY, description="ID de la parada", type=openapi.TYPE_STRING, required=True
            ),
            openapi.Parameter(
                "timestamp", openapi.IN_QUERY, description="Fecha y hora de consulta (YYYY-MM-DDTHH:MM:SS, opcional, por defecto ahora)", type=openapi.TYPE_STRING, required=False
            ),
        ],
        responses={
            200: openapi.Response(
                description="Próximas llegadas a la parada",
                examples={
                    "application/json": {
                        "stop_id": "bUCR-0-01",
                        "timestamp": "2024-05-13T08:00:00",
                        "next_arrivals": [
                            {
                                "trip_id": "1234",
                                "route_id": "R1",
                                "route_short_name": "Línea 1",
                                "route_long_name": "Ruta Central",
                                "trip_headsign": "Centro",
                                "wheelchair_accessible": 1,
                                "in_progress": False,
                                "arrival_time": "2024-05-13T08:15:00Z",
                                "departure_time": "2024-05-13T08:16:00Z",
                                "progression": None
                            },
                            {
                                "trip_id": "5678",
                                "route_id": "R2",
                                "route_short_name": "Línea 2",
                                "route_long_name": "Ruta Norte",
                                "trip_headsign": "Norte",
                                "wheelchair_accessible": 2,
                                "in_progress": True,
                                "arrival_time": "2024-05-13T08:20:00Z",
                                "departure_time": "2024-05-13T08:21:00Z",
                                "progression": {
                                    "position_in_shape": 0.45,
                                    "current_stop_sequence": 7,
                                    "current_status": "IN_TRANSIT_TO",
                                    "occupancy_status": "MANY_SEATS_AVAILABLE"
                                }
                            }
                        ]
                    }
                }
            ),
            400: "Parámetros faltantes o incorrectos",
            404: "No existe la parada especificada",
            204: "No hay servicio disponible para la fecha especificada"
        }
    )

    def get(self, request):
        # TODO: check for errors and exceptions and validations when data is not found

        # Get query parameters (stop and, optionally, timestamp)
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

        current_feed = Feed.objects.filter(is_current=True).latest("retrieved_at")
        service_id = get_calendar(timestamp.date(), current_feed)
        if service_id is None:
            return Response(
                {"error": "No hay servicio disponible para la fecha especificada."},
                status=status.HTTP_204_NO_CONTENT,
            )

        next_arrivals = []

        # For scheduled trips
        stop_times = StopTime.objects.filter(
            feed=current_feed,
            stop_id=stop_id,
            arrival_time__gte=timestamp.time(),
            _trip__service_id=service_id,
        ).order_by("arrival_time")

        # For trips in progress
        latest_trip_update = FeedMessage.objects.filter(
            entity_type="trip_update"
        ).latest("timestamp")
        # TODO: check TTL (time to live)
        stop_time_updates = StopTimeUpdate.objects.filter(
            feed_message=latest_trip_update, stop_id=stop_id
        )

        # Build the response for scheduled trips
        for stop_time in stop_times:
            trip = Trip.objects.filter(
                trip_id=stop_time.trip_id, feed=current_feed
            ).first()
            route = Route.objects.filter(
                route_id=trip.route_id, feed=current_feed
            ).first()

            next_arrivals.append(
                {
                    "trip_id": trip.trip_id,
                    "route_id": route.route_id,
                    "route_short_name": route.route_short_name,
                    "route_long_name": route.route_long_name,
                    "trip_headsign": trip.trip_headsign,
                    "wheelchair_accessible": trip.wheelchair_accessible,
                    "in_progress": False,
                    "arrival_time": datetime.combine(
                        timestamp.today(), stop_time.arrival_time
                    ),
                    "departure_time": datetime.combine(
                        timestamp.today(), stop_time.departure_time
                    ),
                    "progression": None,
                }
            )

        # Build the response for trips in progress
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
    """
    Obtiene la siguiente parada de un viaje específico.

    get:
    Obtiene la siguiente parada de un viaje específico.
    """

    @swagger_auto_schema(
        operation_description="Devuelve la siguiente parada de un viaje específico.",
        manual_parameters=[
            openapi.Parameter(
                "trip_id", openapi.IN_QUERY, description="ID del viaje", type=openapi.TYPE_STRING, required=True
            ),
            openapi.Parameter(
                "start_date", openapi.IN_QUERY, description="Fecha de inicio (YYYY-MM-DD)", type=openapi.TYPE_STRING, required=True
            ),
            openapi.Parameter(
                "start_time", openapi.IN_QUERY, description="Hora de inicio (HH:MM:SS)", type=openapi.TYPE_STRING, required=True
            ),
        ],
        responses={
            200: openapi.Response(
                description="Secuencia de próximas paradas",
                examples={
                    "application/json": {
                        "trip_id": "1234",
                        "start_date": "2024-05-13",
                        "start_time": "08:00:00",
                        "next_stop_sequence": [
                            {
                                "stop_sequence": 5,
                                "stop_id": "STOP_1",
                                "stop_name": "Parada Central",
                                "stop_lat": 9.9333,
                                "stop_lon": -84.0833,
                                "arrival": "2024-05-13T08:15:00Z",
                                "departure": "2024-05-13T08:16:00Z"
                            }
                        ]
                    }
                }
            ),
            400: "Parámetros faltantes o incorrectos",
        }
    )

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
    """
    Obtiene las paradas de una ruta específica.

    get:
    Obtiene las paradas de una ruta específica.
    """

    @swagger_auto_schema(
        operation_description="Devuelve las paradas de una ruta específica en formato GeoJSON.",
        manual_parameters=[
            openapi.Parameter(
                "route_id", openapi.IN_QUERY, description="ID de la ruta", type=openapi.TYPE_STRING, required=True
            ),
            openapi.Parameter(
                "shape_id", openapi.IN_QUERY, description="ID de la trayectoria", type=openapi.TYPE_STRING, required=True
            ),
        ],
        responses={
            200: openapi.Response(
                description="GeoJSON con las paradas de la ruta",
                examples={
                    "application/json": {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Point",
                                    "coordinates": [-84.0833, 9.9333]
                                },
                                "properties": {
                                    "route_id": "bUCR_L1",
                                    "shape_id": "hacia_educacion",
                                    "stop_id": "STOP_1",
                                    "stop_name": "Parada Central",
                                    "stop_desc": "Parada principal",
                                    "stop_sequence": 1,
                                    "timepoint": True,
                                    "wheelchair_boarding": 1
                                }
                            }
                        ]
                    }
                }
            ),
            400: "Parámetros faltantes o incorrectos",
            404: "No existe la combinación de ruta y trayectoria en la base de datos"
        }
    )

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

    retrieve:
    Obtiene una agencia de transporte público específica.

    list:
    Lista todas las agencias de transporte público.

    create:
    Crea una nueva agencia de transporte público.

    update:
    Actualiza una agencia de transporte público existente.

    delete:
    Elimina una agencia de transporte público existente.

    partial_update:
    Actualiza parcialmente una agencia de transporte público existente.
    """

    queryset = Agency.objects.all()
    serializer_class = AgencySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["agency_id", "agency_name"]
    # permission_classes = [permissions.IsAuthenticated]


class StopViewSet(viewsets.ModelViewSet):
    """
    Paradas de transporte público.

    retrieve:
    Obtiene una parada de transporte público específica.

    list:
    Lista todas las paradas de transporte público.

    create:
    Crea una nueva parada de transporte público.

    update:
    Actualiza una parada de transporte público existente.

    delete:
    Elimina una parada de transporte público existente.

    partial_update:
    Actualiza parcialmente una parada de transporte público existente.
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

    retrieve:
    Obtiene una ruta de transporte público específica.

    list:
    Lista todas las rutas de transporte público.

    create:
    Crea una nueva ruta de transporte público.

    update:
    Actualiza una ruta de transporte público existente.

    delete:
    Elimina una ruta de transporte público existente.

    partial_update:
    Actualiza parcialmente una ruta de transporte público existente.
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
    
    retrieve:
    Obtiene un calendario de transporte público específico.

    list:
    Lista todos los calendarios de transporte público.

    create:
    Crea un nuevo calendario de transporte público.

    update:
    Actualiza un calendario de transporte público existente.

    delete:
    Elimina un calendario de transporte público existente.

    partial_update:
    Actualiza parcialmente un calendario de transporte público existente.
    """

    queryset = Calendar.objects.all()
    serializer_class = CalendarSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["service_id"]
    # permission_classes = [permissions.IsAuthenticated]


class CalendarDateViewSet(viewsets.ModelViewSet):
    """
    Fechas de calendario de transporte público.

    retrieve:
    Obtiene una fecha de calendario de transporte público específica.

    list:
    Lista todas las fechas de calendario de transporte público.

    create:
    Crea una nueva fecha de calendario de transporte público.

    update:
    Actualiza una fecha de calendario de transporte público existente.

    delete:
    Elimina una fecha de calendario de transporte público existente.

    partial_update:
    Actualiza parcialmente una fecha de calendario de transporte público existente.
    """

    queryset = CalendarDate.objects.all()
    serializer_class = CalendarDateSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["service_id"]
    # permission_classes = [permissions.IsAuthenticated]


class ShapeViewSet(viewsets.ModelViewSet):
    """
    Formas de transporte público.

    retrieve:
    Obtiene una forma de transporte público específica.

    list:
    Lista todas las formas de transporte público.

    create:
    Crea una nueva forma de transporte público.

    update:
    Actualiza una forma de transporte público existente.

    delete:
    Elimina una forma de transporte público existente.

    partial_update:
    Actualiza parcialmente una forma de transporte público existente.
    """

    queryset = Shape.objects.all()
    serializer_class = ShapeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id"]
    # permission_classes = [permissions.IsAuthenticated]


class GeoShapeViewSet(viewsets.ModelViewSet):
    """
    Formas geográficas de transporte público.

    retrieve:
    Obtiene una forma geográfica de transporte público específica.

    list:
    Lista todas las formas geográficas de transporte público.

    create:
    Crea una nueva forma geográfica de transporte público.

    update:
    Actualiza una forma geográfica de transporte público existente.

    delete:
    Elimina una forma geográfica de transporte público existente.

    partial_update:
    Actualiza parcialmente una forma geográfica de transporte público existente.
    """

    queryset = GeoShape.objects.all()
    serializer_class = GeoShapeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["shape_id"]
    # permission_classes = [permissions.IsAuthenticated]


class TripViewSet(viewsets.ModelViewSet):
    """
    Viajes de transporte público.

    retrieve:
    Obtiene un viaje de transporte público específico.

    list:
    Lista todos los viajes de transporte público.

    create:
    Crea un nuevo viaje de transporte público.

    update:
    Actualiza un viaje de transporte público existente.

    delete:
    Elimina un viaje de transporte público existente.

    partial_update:
    Actualiza parcialmente un viaje de transporte público existente.
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

    retrieve:
    Obtiene un horario de parada de transporte público específico.

    list:
    Lista todos los horarios de paradas de transporte público.

    create:
    Crea un nuevo horario de parada de transporte público.

    update:
    Actualiza un horario de parada de transporte público existente.

    delete:
    Elimina un horario de parada de transporte público existente.

    partial_update:
    Actualiza parcialmente un horario de parada de transporte público existente.
    """

    queryset = StopTime.objects.all()
    serializer_class = StopTimeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["trip_id", "stop_id"]
    # permission_classes = [permissions.IsAuthenticated]


class FeedInfoViewSet(viewsets.ModelViewSet):
    """
    Información de alimentación de transporte público.

    retrieve:
    Obtiene información de alimentación de transporte público específica.

    list:
    Lista toda la información de alimentación de transporte público.

    create:
    Crea nueva información de alimentación de transporte público.

    update:
    Actualiza información de alimentación de transporte público existente.

    delete:
    Elimina información de alimentación de transporte público existente.

    partial_update:
    Actualiza parcialmente información de alimentación de transporte público existente.
    """

    queryset = FeedInfo.objects.all()
    serializer_class = FeedInfoSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["feed_publisher_name"]
    # permission_classes = [permissions.IsAuthenticated]


class FareAttributeViewSet(viewsets.ModelViewSet):
    """
    Atributos de tarifa de transporte público.

    retrieve:
    Obtiene un atributo de tarifa de transporte público específico.

    list:
    Lista todos los atributos de tarifa de transporte público.

    create:
    Crea un nuevo atributo de tarifa de transporte público.

    update:
    Actualiza un atributo de tarifa de transporte público existente.

    delete:
    Elimina un atributo de tarifa de transporte público existente.

    partial_update:
    Actualiza parcialmente un atributo de tarifa de transporte público existente.
    """

    queryset = FareAttribute.objects.all()
    serializer_class = FareAttributeSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["fare_id", "price", "currency_type", "payment_method", "agency_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class FareRuleViewSet(viewsets.ModelViewSet):
    """
    Reglas de tarifa de transporte público.

    retrieve:
    Obtiene una regla de tarifa de transporte público específica.

    list:
    Lista todas las reglas de tarifa de transporte público.

    create:
    Crea una nueva regla de tarifa de transporte público.

    update:
    Actualiza una regla de tarifa de transporte público existente.

    delete:
    Elimina una regla de tarifa de transporte público existente.

    partial_update:
    Actualiza parcialmente una regla de tarifa de transporte público existente.
    """

    queryset = FareRule.objects.all()
    serializer_class = FareRuleSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["fare_id", "route_id", "origin_id", "destination_id"]
    # permission_classes = [permissions.IsAuthenticated]
    # Esto no tiene path con query params ni response schema


class ServiceAlertViewSet(viewsets.ModelViewSet):
    """
    Alertas de servicio de transporte público.

    retrieve:
    Obtiene una alerta de servicio específica.
    
    list:
    Lista todas las alertas de servicio.
    
    create:
    Crea una nueva alerta de servicio.
    
    update:
    Actualiza una alerta de servicio existente.
    
    delete:
    Elimina una alerta de servicio existente.
    
    partial_update:
    Actualiza parcialmente una alerta de servicio existente.
    """

    queryset = Alert.objects.all()
    serializer_class = ServiceAlertSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = [
        "alert_id", "effect", "route_id", "trip_id", "service_date", "service_start_time", "service_end_time", "alert_description"
    ]
    # permission_classes = [permissions.IsAuthenticated]


class WeatherViewSet(viewsets.ModelViewSet):
    """
    Condiciones climáticas.

    retrieve:
    Obtiene una condición climática específica.

    list:
    Lista todas las condiciones climáticas.

    create:
    Crea una nueva condición climática.

    update:
    Actualiza una condición climática existente.

    delete:
    Elimina una condición climática existente.

    partial_update:
    Actualiza parcialmente una condición climática existente.
    """

    queryset = Weather.objects.all()
    serializer_class = WeatherSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["weather_location", "weather_condition"]
    # permission_classes = [permissions.IsAuthenticated]


class SocialViewSet(viewsets.ModelViewSet):
    """
    Publicaciones en redes sociales.

    retrieve:
    Obtiene una publicación en redes sociales específica.

    list:
    Lista todas las publicaciones en redes sociales.

    create:
    Crea una nueva publicación en redes sociales.

    update:
    Actualiza una publicación en redes sociales existente.

    delete:
    Elimina una publicación en redes sociales existente.

    partial_update:
    Actualiza parcialmente una publicación en redes sociales existente.
    """

    queryset = Social.objects.all()
    serializer_class = SocialSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["social_media", "social_content", "social_location"]
    # permission_classes = [permissions.IsAuthenticated]


class FeedMessageViewSet(viewsets.ModelViewSet):
    """
    Mensajes de alimentación.

    retrieve:
    Obtiene un mensaje de alimentación específico.

    list:
    Lista todos los mensajes de alimentación.

    create:
    Crea un nuevo mensaje de alimentación.

    update:
    Actualiza un mensaje de alimentación existente.

    delete:
    Elimina un mensaje de alimentación existente.

    partial_update:
    Actualiza parcialmente un mensaje de alimentación existente.
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

    retrieve:
    Obtiene una actualización de viaje específica.

    list:
    Lista todas las actualizaciones de viaje.

    create:
    Crea una nueva actualización de viaje.

    update:
    Actualiza una actualización de viaje existente.

    delete:
    Elimina una actualización de viaje existente.

    partial_update:
    Actualiza parcialmente una actualización de viaje existente.
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

    retrieve:
    Obtiene una actualización de horario de parada específica.

    list:
    Lista todas las actualizaciones de horario de parada.

    create:
    Crea una nueva actualización de horario de parada.

    update:
    Actualiza una actualización de horario de parada existente.

    delete:
    Elimina una actualización de horario de parada existente.

    partial_update:
    Actualiza parcialmente una actualización de horario de parada existente.
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

    retrieve:
    Obtiene una posición de vehículo específica.

    list:
    Lista todas las posiciones de vehículos.

    create:
    Crea una nueva posición de vehículo.

    update:
    Actualiza una posición de vehículo existente.

    delete:
    Elimina una posición de vehículo existente.

    partial_update:
    Actualiza parcialmente una posición de vehículo existente.
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

    retrieve:
    Obtiene una aplicación específica.

    list:
    Lista todas las aplicaciones.

    create:
    Crea una nueva aplicación.

    update:
    Actualiza una aplicación existente.

    delete:
    Elimina una aplicación existente.

    partial_update:
    Actualiza parcialmente una aplicación existente.
    """

    queryset = InfoService.objects.all()
    serializer_class = InfoServiceSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["type", "name"]
    # permission_classes = [permissions.IsAuthenticated]


class InfoProviderViewSet(viewsets.ModelViewSet):
    """
    Proveedores de servicios conectados al servidor de datos.

    retrieve:
    Obtiene un proveedor de servicios específico.

    list:
    Lista todos los proveedores de servicios.

    create:
    Crea un nuevo proveedor de servicios.

    update:
    Actualiza un proveedor de servicios existente.

    delete:
    Elimina un proveedor de servicios existente.

    partial_update:
    Actualiza parcialmente un proveedor de servicios existente.
    """

    queryset = InfoProvider.objects.all()
    serializer_class = InfoProviderSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["name"]
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
        service_id = calendar.service_id

    return service_id
