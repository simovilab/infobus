from django.urls import re_path

from .consumers import UpdatesConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/updates/$",
        UpdatesConsumer.as_asgi(),
    ),
]

"""
Posible mapeo de endpoints WebSocket:
- ws/stop-time-update/<"stop"|"vehicle">/<entity_id>/ -> StopTimeUpdateConsumer
- ws/<run_id>/position/ -> PositionConsumer
- ws/<run_id>/vehicle-stop-status/ -> VehicleStopStatusConsumer
- ws/<run_id>/congestion-level/ -> CongestionLevelConsumer
- ws/<run_id>/occupancy-status/ -> OccupancyStatusConsumer

Cada vez que un viaje (run) comienza, las paradas asociadas 
a ese viaje se suscriben a los endpoints correspondientes usando el run_id. 
Esto permite que cada parada reciba actualizaciones en tiempo real sobre el estado 
del viaje, como la posición del vehículo, el nivel de congestión, el estado de ocupación, etc.

Necesitamos una máquina de estados para cada viaje (run)
para darle permanencia a cada viaje y manejar su ciclo de vida
y eventualidades (pérdida de comunicación, etc).

ws/realtime/

{
    "type": "screen",
    "stop_id": "ABC123",
}

{
    "type": "web",
    "page": "route",
    "route_id": "B23"
}

{
  "action": "subscribe",
  "topic": "trip.stop_time_updates",
  "run_id": "FTR456"
}

Topic anatomy: <entity>.<info>[.<namespace>].<instance>.<attribute>
Entity: the GTFS entity (trip, stop, route, alert, etc)
Info: the type of information or aspect of the entity (stop_time_updates, vehicle_positions, alerts, etc)
Namespace: an optional further categorization to create a new namespace for related topics (e.g., alert types, route types, etc)
Instance: the specific identifier for the entity instance (run_id, stop_id, route_id, etc)
Note: run_id is an instance of trip

Topic: "trip.stop_time_updates.<run_id>" (periodic updated)
Topic: "trip.vehicle_stop_status.<run_id>" (event-driven update)
Topic: "trip.congestion_level.<run_id>" (event-driven update)
Topic: "trip.occupancy_status.<run_id>" (event-driven update)
Topic: "trip.alerts.<run_id>" (event-driven update)
Topic: "stop.stop_time_updates.<stop_id>" (periodic updated)
Topic: "stop.vehicle_positions.<stop_id>" (periodic updated)
Topic: "stop.alerts.<stop_id>" (event-driven update)
Topic: "route.vehicle_positions.<route_id>" (periodic updated)
Topic: "route.alerts.<route_id>" (event-driven update)
Topic: "route.alerts.type.<route_type>" (event-driven update)
Topic: "route.alerts.<route_id>.<direction_id>" (event-driven update)
Topic: "agency.alerts.<agency_id>" (event-driven update)

Topics in Channels are mapped 1:1 to keys on Redis.

Key: "trip:stop_time_updates:<run_id>"
Key: "trip:vehicle_stop_status:<run_id>"
Key: "trip:congestion_level:<run_id>"
Key: "trip:occupancy_status:<run_id>"
Key: "trip:alerts:<run_id>"
Key: "stop:stop_time_updates:<stop_id>"
Key: "stop:vehicle_positions:<stop_id>"
Key: "stop:alerts:<stop_id>"
Key: "route:vehicle_positions:<route_id>"
Key: "route:alerts:<route_id>"
Key: "route:alerts.type:<route_type>"
Key: "route:alerts:<route_id>.<direction_id>"
Key: "agency:alerts:<agency_id>"

"""
