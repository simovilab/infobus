"""
WebSocket URL Routing

Defines URL patterns for WebSocket connections following the AsyncAPI specification.

URLs:
- ws/trip/{trip_id} → TripConsumer
- ws/route/{route_id} → RouteConsumer  
- ws/route/{route_id}/direction/{direction_id} → RouteConsumer (filtered)
"""

from django.urls import re_path

# Consumers will be imported once implemented
# from websocket.consumers.trip import TripConsumer
# from websocket.consumers.route import RouteConsumer

websocket_urlpatterns = [
    # Will be populated in TURNO 2-3
    # re_path(r'^ws/trip/(?P<trip_id>[^/]+)$', TripConsumer.as_asgi()),
    # re_path(r'^ws/route/(?P<route_id>[^/]+)$', RouteConsumer.as_asgi()),
    # re_path(r'^ws/route/(?P<route_id>[^/]+)/direction/(?P<direction_id>[01])$',
    #         RouteConsumer.as_asgi()),
]
