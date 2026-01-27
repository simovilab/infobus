from django.urls import re_path

from .consumers import StatusConsumer
from websocket.consumers.trip import TripConsumer
from websocket.consumers.route import RouteConsumer

websocket_urlpatterns = [
    re_path(r"ws/status/?$", StatusConsumer.as_asgi()),
    re_path(r"ws/trips/(?P<trip_id>[^/]+)/?$", TripConsumer.as_asgi()),
    re_path(r"ws/route/(?P<route_id>[^/]+)/?$", RouteConsumer.as_asgi()),
    re_path(r"ws/route/(?P<route_id>[^/]+)/direction/(?P<direction_id>[01])/?$", RouteConsumer.as_asgi()),
]
