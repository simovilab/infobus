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
- ws/service/<screen_id>/ -> ServiceConsumer

Cada vez que un viaje (run) comienza, las paradas asociadas 
a ese viaje se suscriben a los endpoints correspondientes usando el run_id. 
Esto permite que cada parada reciba actualizaciones en tiempo real sobre el estado 
del viaje, como la posición del vehículo, el nivel de congestión, el estado de ocupación, etc.

Necesitamos una máquina de estados para cada viaje (run)
para darle permanencia a cada viaje y manejar su ciclo de vida
y eventualidades (pérdida de comunicación, etc).
"""
