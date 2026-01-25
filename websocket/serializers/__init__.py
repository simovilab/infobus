"""
GTFS-Realtime Serializers

This module provides serialization functions to convert Django ORM models
to JSON payloads following the AsyncAPI specification.

Available Serializers:
- serialize_trip_update: TripUpdate model → TripUpdatePayload
- serialize_vehicle_position: VehiclePosition model → VehiclePositionPayload
- serialize_stop_time_update: StopTimeUpdate model → StopTimeUpdate schema
- serialize_route_vehicles: Query → RouteVehiclesPayload (snapshot)
"""

from .gtfs import (
    serialize_trip_update,
    serialize_vehicle_position,
    serialize_stop_time_update,
    serialize_route_vehicles,
)

__all__ = [
    "serialize_trip_update",
    "serialize_vehicle_position",
    "serialize_stop_time_update",
    "serialize_route_vehicles",
]
