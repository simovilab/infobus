"""
ASGI config for datahub project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

from feed.routing import websocket_urlpatterns as feed_ws_patterns
from websocket.routing import websocket_urlpatterns as websocket_ws_patterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "datahub.settings")

# Combine WebSocket URL patterns from both apps
all_websocket_urlpatterns = feed_ws_patterns + websocket_ws_patterns

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": URLRouter(all_websocket_urlpatterns),
    }
)
