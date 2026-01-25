"""
WebSocket URL Routing

Defines URL patterns for WebSocket connections following the AsyncAPI specification.

URLs:
- ws/trip/{trip_id} → TripConsumer
- ws/route/{route_id} → RouteConsumer  
- ws/route/{route_id}/direction/{direction_id} → RouteConsumer (filtered)
"""

from django.urls import re_path
from websocket.consumers.trip import TripConsumer
from websocket.consumers.route import RouteConsumer

websocket_urlpatterns = [
    # Trip consumer - single trip updates
    re_path(r'ws/trips/(?P<trip_id>[^/]+)/$', TripConsumer.as_asgi()),
    
    # Route consumer - all vehicles on route (both directions)
    re_path(r'ws/route/(?P<route_id>[^/]+)/$', RouteConsumer.as_asgi()),
    
    # Route consumer - vehicles filtered by direction (0 or 1)
    re_path(r'ws/route/(?P<route_id>[^/]+)/direction/(?P<direction_id>[01])/$', RouteConsumer.as_asgi()),
]
