"""
GTFS-Realtime Serializers

Converts Django ORM models to JSON payloads following AsyncAPI 3.0 specification.

These serializers map GTFS-Realtime database models to the schema defined in
/docs/asyncapi/asyncapi-websocket-spec.yaml

Author: Brandon Trigueros Lara
Date: January 23, 2026
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import pytz

from gtfs.models import TripUpdate, VehiclePosition, StopTimeUpdate, Route


def serialize_trip_update(
    trip_update: TripUpdate,
    include_stops: bool = True,
    include_shape: bool = False,
) -> Dict[str, Any]:
    """
    Serialize TripUpdate model to TripUpdatePayload schema.

    Args:
        trip_update: TripUpdate instance from database (with prefetched relations)
        include_stops: Include stop_time_updates array (default: True)
        include_shape: Include route shape geometry (default: False)

    Returns:
        Dictionary following TripUpdatePayload schema from AsyncAPI spec

    Example:
        >>> trip = TripUpdate.objects.select_related('feed_message').prefetch_related('stoptimeupdate_set').get(trip_trip_id="CR-SJ-01-123")
        >>> payload = serialize_trip_update(trip, include_stops=True)
        >>> print(payload['trip']['trip_id'])
        'CR-SJ-01-123'
    
    Note:
        This function does NOT make database queries. All related data
        should be prefetched by the caller using select_related/prefetch_related.
    """
    payload: Dict[str, Any] = {
        "trip": {
            "trip_id": trip_update.trip_trip_id or "",
            "route_id": trip_update.trip_route_id or "",
            "direction_id": trip_update.trip_direction_id if trip_update.trip_direction_id is not None else 0,
            "start_time": str(trip_update.trip_start_time) if trip_update.trip_start_time else None,
            "start_date": trip_update.trip_start_date.isoformat() if trip_update.trip_start_date else None,
            "schedule_relationship": trip_update.trip_schedule_relationship or "SCHEDULED",
        },
        "vehicle": {
            "id": trip_update.vehicle_id or "",
            "label": trip_update.vehicle_label or "",
            "license_plate": trip_update.vehicle_license_plate,
        },
        "timestamp": trip_update.timestamp.isoformat() if trip_update.timestamp else None,
        "delay": trip_update.delay or 0,
    }

    # Add stop time updates if requested
    if include_stops:
        stop_updates = list(trip_update.stoptimeupdate_set.all())
        if stop_updates:
            payload["stop_time_updates"] = [
                serialize_stop_time_update(stu) for stu in stop_updates
            ]

    return payload


def serialize_vehicle_position(
    vehicle_pos: VehiclePosition,
) -> Dict[str, Any]:
    """
    Serialize VehiclePosition model to VehiclePositionPayload schema.

    Args:
        vehicle_pos: VehiclePosition instance from database

    Returns:
        Dictionary following VehiclePositionPayload schema

    Example:
        >>> vp = VehiclePosition.objects.latest('vehicle_timestamp')
        >>> payload = serialize_vehicle_position(vp)
        >>> print(payload['position']['latitude'])
        9.9281
    """
    payload: Dict[str, Any] = {
        "trip": {
            "trip_id": vehicle_pos.vehicle_trip_trip_id or "",
            "route_id": vehicle_pos.vehicle_trip_route_id or "",
            "direction_id": vehicle_pos.vehicle_trip_direction_id
            if vehicle_pos.vehicle_trip_direction_id is not None
            else 0,
            "start_time": (
                str(vehicle_pos.vehicle_trip_start_time)
                if vehicle_pos.vehicle_trip_start_time
                else None
            ),
            "start_date": (
                vehicle_pos.vehicle_trip_start_date.isoformat()
                if vehicle_pos.vehicle_trip_start_date
                else None
            ),
        },
        "vehicle": {
            "id": vehicle_pos.vehicle_vehicle_id or "",
            "label": vehicle_pos.vehicle_vehicle_label or "",
            "license_plate": vehicle_pos.vehicle_vehicle_license_plate,
        },
        "position": {
            "latitude": vehicle_pos.vehicle_position_latitude,
            "longitude": vehicle_pos.vehicle_position_longitude,
            "bearing": vehicle_pos.vehicle_position_bearing,
            "speed": vehicle_pos.vehicle_position_speed,
            "odometer": vehicle_pos.vehicle_position_odometer,
        },
        "current_stop_sequence": vehicle_pos.vehicle_current_stop_sequence,
        "stop_id": vehicle_pos.vehicle_stop_id,
        "current_status": vehicle_pos.vehicle_current_status or "IN_TRANSIT_TO",
        "timestamp": (
            vehicle_pos.vehicle_timestamp.isoformat()
            if vehicle_pos.vehicle_timestamp
            else datetime.now(pytz.UTC).isoformat()
        ),
        "congestion_level": vehicle_pos.vehicle_congestion_level,
        "occupancy_status": vehicle_pos.vehicle_occupancy_status,
    }

    return payload


def serialize_stop_time_update(stop_update: StopTimeUpdate) -> Dict[str, Any]:
    """
    Serialize StopTimeUpdate model to StopTimeUpdate schema.

    Args:
        stop_update: StopTimeUpdate instance from database

    Returns:
        Dictionary following StopTimeUpdate schema

    Example:
        >>> stu = StopTimeUpdate.objects.first()
        >>> payload = serialize_stop_time_update(stu)
        >>> print(payload['stop_id'])
        'STOP_123'
    """
    payload: Dict[str, Any] = {
        "stop_sequence": stop_update.stop_sequence or 0,
        "stop_id": stop_update.stop_id or "",
        "schedule_relationship": stop_update.schedule_relationship or "SCHEDULED",
    }

    # Add arrival info if available
    if stop_update.arrival_time or stop_update.arrival_delay is not None:
        payload["arrival"] = {
            "delay": stop_update.arrival_delay or 0,
            "time": (
                stop_update.arrival_time.isoformat()
                if stop_update.arrival_time
                else None
            ),
            "uncertainty": stop_update.arrival_uncertainty,
        }

    # Add departure info if available
    if stop_update.departure_time or stop_update.departure_delay is not None:
        payload["departure"] = {
            "delay": stop_update.departure_delay or 0,
            "time": (
                stop_update.departure_time.isoformat()
                if stop_update.departure_time
                else None
            ),
            "uncertainty": stop_update.departure_uncertainty,
        }

    return payload


def serialize_route_vehicles(
    route_id: str,
    direction_id: Optional[int] = None,
    provider_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Serialize all active vehicles on a route to RouteVehiclesPayload schema.

    This creates a snapshot of all vehicles currently operating on the specified route.
    Used for route-level WebSocket subscriptions.

    Args:
        route_id: GTFS route_id to query
        direction_id: Optional direction filter (0 or 1), None for both directions
        provider_code: Optional GTFS provider code filter

    Returns:
        Dictionary following RouteVehiclesPayload schema with vehicles array

    Example:
        >>> payload = serialize_route_vehicles("ROUTE_001", direction_id=0)
        >>> print(f"Found {payload['count']} vehicles")
        Found 5 vehicles
    """
    # Build query
    query = VehiclePosition.objects.filter(vehicle_trip_route_id=route_id)

    # Filter by direction if specified
    if direction_id is not None:
        query = query.filter(vehicle_trip_direction_id=direction_id)

    # Filter by provider if specified
    if provider_code:
        query = query.filter(feed_message__provider__code=provider_code)

    # Get latest position for each unique vehicle
    # Group by vehicle_id and get latest timestamp
    from django.db.models import Max

    latest_timestamps = (
        query.values("vehicle_vehicle_id")
        .annotate(latest=Max("vehicle_timestamp"))
        .values("vehicle_vehicle_id", "latest")
    )

    vehicle_positions = []
    for item in latest_timestamps:
        try:
            vp = query.get(
                vehicle_vehicle_id=item["vehicle_vehicle_id"],
                vehicle_timestamp=item["latest"],
            )
            vehicle_positions.append(vp)
        except VehiclePosition.DoesNotExist:
            continue

    # Serialize all vehicles
    vehicles = [serialize_vehicle_position(vp) for vp in vehicle_positions]

    payload: Dict[str, Any] = {
        "route_id": route_id,
        "direction_id": direction_id,  # None if both directions
        "timestamp": datetime.now(pytz.UTC).isoformat(),
        "count": len(vehicles),
        "vehicles": vehicles,
    }

    return payload


# Helper function to clean None values from dict (optional)
def _clean_none_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively remove keys with None values from dictionary.

    This is useful for reducing payload size in WebSocket messages.
    """
    if not isinstance(data, dict):
        return data

    return {
        key: _clean_none_values(value) if isinstance(value, dict) else value
        for key, value in data.items()
        if value is not None
    }
