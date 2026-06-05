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
    re_path(r"ws/status/$", StatusConsumer.as_asgi()),
]
