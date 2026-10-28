"""
ASGI config for infobus project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "infobus.settings")
# Initialize the app registry before WebSocket routing imports Django models.
django_asgi_application = get_asgi_application()

from updates.routing import websocket_urlpatterns as updates_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_application,
        "websocket": URLRouter(updates_urlpatterns),
    }
)
