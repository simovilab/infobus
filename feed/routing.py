from django.urls import re_path

from .consumers import StatusConsumer
from websocket.consumers.trip import TripConsumer

websocket_urlpatterns = [
    re_path(r"ws/status/?$", StatusConsumer.as_asgi()),
    re_path(r"ws/trips/(?P<trip_id>[^/]+)/?$", TripConsumer.as_asgi()),
]
