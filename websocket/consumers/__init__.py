"""
WebSocket Consumers for GTFS-Realtime

This module contains Django Channels WebSocket consumers for handling
real-time transit data subscriptions.

Available Consumers:
- TripConsumer: Handles subscriptions to specific trip updates
- RouteConsumer: Handles subscriptions to route-level vehicle updates
"""

from websocket.consumers.trip import TripConsumer

__all__ = ['TripConsumer']

