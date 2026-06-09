from django.urls import re_path

from .consumers import WebConsumer, ScreenConsumer, StatusConsumer

websocket_urlpatterns = [
    re_path(
        r"ws/screen/(?P<screen_type>\w+)/(?P<screen_id>[\w-]+)/$",
        ScreenConsumer.as_asgi(),
    ),
    re_path(
        r"ws/web/(?P<web_component>\w+)/(?P<element_id>[\w-]+)/$",
        WebConsumer.as_asgi(),
    ),
    re_path(
        r"ws/alerts/(?P<informed_entity>\w+)/(?P<entity_id>[\w-]+)/$",
        WebConsumer.as_asgi(),
    ),
    re_path(r"ws/status/$", StatusConsumer.as_asgi()),
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
  "topic": "run.stop_time_updates",
  "run_id": "FTR456"
}

Topic: "run.stop_time_updates.<run_id>"
Topic: "run.vehicle_stop_status.<run_id>"
Topic: "run.congestion_level.<run_id>"
Topic: "run.occupancy_status.<run_id>"
Topic: "stop.stop_time_updates.<stop_id>"
Topic: "stop.vehicle_positions.<stop_id>"
Topic: "route.vehicle_positions.<route_id>"
Topic: "alerts.agency_id.<agency_id>"
Topic: "alerts.route_id.<route_id>"
Topic: "alerts.route_type.<route_type>"
Topic: "alerts.direction_id.<direction_id>"
Topic: "alerts.run_id.<run_id>"
Topic: "alerts.stop_id.<stop_id>"

Redis: "run:vehicle_stop_status:<run_id>" (ARRIVING_AT, STOPPED_AT)
Redis: "runs:in_progress"


"""
