"""
WebSocket Consumer for GTFS-Realtime Route Updates.

Handles real-time updates for all vehicles operating on a specific route,
with optional filtering by direction.

Example Usage:
    URL 1: ws://localhost:8000/ws/route/ROUTE_001
    URL 2: ws://localhost:8000/ws/route/ROUTE_001/direction/0
    
    Client receives:
    {
        "type": "route.snapshot",
        "route_id": "ROUTE_001",
        "direction_id": 0,
        "timestamp": "2026-01-25T10:30:00Z",
        "count": 5,
        "vehicles": [
            {
                "trip": {"trip_id": "TRIP_123", "route_id": "ROUTE_001"},
                "vehicle": {"id": "BUS_001", "label": "101"},
                "position": {"latitude": 9.9355, "longitude": -84.0795},
                "timestamp": "2026-01-25T10:30:00Z"
            },
            ...
        ]
    }
"""

import json
import logging
from typing import Optional, List
from datetime import timedelta

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from gtfs.models import Route, VehiclePosition

logger = logging.getLogger(__name__)


class RouteConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time route updates.
    
    Clients connect to /ws/route/{route_id} to receive updates for all vehicles
    on that route, or /ws/route/{route_id}/direction/{direction_id} to filter
    by direction (0 or 1).
    
    Error Codes:
        4000: Invalid direction_id (must be 0 or 1)
        4004: Route not found in database
        5001: Internal server error
    """
    
    # Error codes (AsyncAPI compliant)
    ERR_INVALID_PARAMS = 4000
    ERR_ROUTE_NOT_FOUND = 4004
    ERR_SERVER_ERROR = 5001
    
    async def connect(self):
        """
        Accept WebSocket connection and subscribe to route updates.
        
        Validates route exists, parses direction parameter, adds client to
        channel group, and sends initial snapshot.
        
        URL patterns:
            - /ws/route/{route_id} - All directions
            - /ws/route/{route_id}/direction/{direction_id} - Specific direction
        """
        try:
            # Extract route_id from URL path
            self.route_id = self.scope['url_route']['kwargs']['route_id']
            
            # Extract direction_id (optional) from URL path
            self.direction_id = self.scope['url_route']['kwargs'].get('direction_id')
            
            # Validate direction_id if provided
            if self.direction_id is not None:
                direction_int = int(self.direction_id)
                if direction_int not in (0, 1):
                    logger.warning(f"Invalid direction_id: {self.direction_id}")
                    await self.close(code=self.ERR_INVALID_PARAMS)
                    return
                self.direction_id = direction_int
            
            # NOTE: We don't validate route exists in DB because VehiclePosition 
            # may have route_ids that aren't in Route table yet (they come from GTFS-RT feed)
            # The consumer will work with any route_id and just return empty snapshots
            # if there are no vehicles for that route
            
            # Generate group name based on direction filter
            if self.direction_id is not None:
                self.group_name = f"route_{self.route_id}_dir_{self.direction_id}"
            else:
                self.group_name = f"route_{self.route_id}"
            
            # Add to channel layer group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            # Accept connection
            await self.accept()
            logger.info(f"Client connected to route {self.route_id} (direction: {self.direction_id})")
            
            # Send initial snapshot
            await self.send_initial_snapshot()
            
        except ValueError as e:
            logger.error(f"Invalid parameters: {e}")
            await self.close(code=self.ERR_INVALID_PARAMS)
        except Exception as e:
            route_id = getattr(self, 'route_id', 'unknown')
            logger.exception(f"Error connecting to route {route_id}: {e}")
            await self.close(code=self.ERR_SERVER_ERROR)
    
    async def disconnect(self, close_code):
        """
        Remove client from channel group on disconnect.
        
        Args:
            close_code: WebSocket close code
        """
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            logger.info(f"Client disconnected from route {self.route_id} (code: {close_code})")
    
    async def route_update(self, event):
        """
        Receive broadcast from Celery task and forward to client.
        
        Called when channel_layer.group_send() is invoked with type='route.update'.
        
        Event structure from tasks.py:
            {
                "type": "route.update",
                "vehicles": [...]  # Already serialized by serialize_vehicle_position
            }
        
        Args:
            event: Event dict from channel layer
        """
        try:
            # Get vehicles from the broadcast (already serialized by Celery task)
            vehicles = event.get('vehicles', [])
            
            # Build payload for client
            payload = {
                'route_id': self.route_id,
                'direction_id': self.direction_id,
                'timestamp': timezone.now().isoformat(),
                'count': len(vehicles),
                'type': 'route.update',
                'vehicles': vehicles
            }
            
            # Send JSON to client
            await self.send(text_data=json.dumps(payload))
            logger.debug(f"Sent update for route {self.route_id} with {len(vehicles)} vehicles")
            
        except Exception as e:
            logger.exception(f"Error sending route update: {e}")
            # Don't close connection on serialization errors, just log
    
    @database_sync_to_async
    def route_exists(self) -> bool:
        """
        Check if route exists in GTFS Schedule database.
        
        Returns:
            bool: True if route exists, False otherwise
        """
        return Route.objects.filter(route_id=self.route_id).exists()
    
    @database_sync_to_async
    def get_active_vehicles(self) -> List[VehiclePosition]:
        """
        Fetch active vehicles on this route from database.
        
        Filters vehicles by:
        - route_id (required)
        - direction_id (if consumer is subscribed to specific direction)
        - Recent timestamp (last 5 minutes)
        
        Returns:
            List[VehiclePosition]: List of active vehicle positions
        """
        # Only show vehicles from last 5 minutes
        cutoff = timezone.now() - timedelta(minutes=5)
        
        # Start with route filter
        qs = VehiclePosition.objects.filter(
            vehicle_trip_route_id=self.route_id,
            vehicle_timestamp__gte=cutoff
        )
        
        # Add direction filter if subscribed to specific direction
        if self.direction_id is not None:
            qs = qs.filter(vehicle_trip_direction_id=self.direction_id)
        
        # Select related for performance
        qs = qs.select_related('feed_message')
        
        # Order by timestamp descending and get unique vehicles
        # (in case there are duplicates, get the most recent)
        vehicles = {}
        for vp in qs.order_by('-vehicle_timestamp'):
            vehicle_id = vp.vehicle_vehicle_id
            if vehicle_id and vehicle_id not in vehicles:
                vehicles[vehicle_id] = vp
        
        return list(vehicles.values())
    
    async def send_initial_snapshot(self):
        """
        Send current state of route to newly connected client.
        
        Fetches all active vehicles from database and sends as initial message
        with type 'route.snapshot'.
        """
        try:
            vehicles = await self.get_active_vehicles()
            
            # Build payload manually (serialize_route_vehicles has sync DB calls)
            payload = {
                'route_id': self.route_id,
                'direction_id': self.direction_id,
                'timestamp': timezone.now().isoformat(),
                'count': len(vehicles),
                'type': 'route.snapshot',
                'vehicles': [
                    {
                        "trip": {
                            "trip_id": v.vehicle_trip_trip_id or "",
                            "route_id": v.vehicle_trip_route_id or "",
                            "direction_id": v.vehicle_trip_direction_id if v.vehicle_trip_direction_id is not None else 0,
                        },
                        "vehicle": {
                            "id": v.vehicle_vehicle_id or "",
                            "label": v.vehicle_vehicle_label or "",
                            "license_plate": v.vehicle_vehicle_license_plate,
                        },
                        "position": {
                            "latitude": v.vehicle_position_latitude,
                            "longitude": v.vehicle_position_longitude,
                            "bearing": v.vehicle_position_bearing,
                            "speed": v.vehicle_position_speed,
                        },
                        "timestamp": v.vehicle_timestamp.isoformat() if v.vehicle_timestamp else None,
                    }
                    for v in vehicles
                ]
            }
            
            await self.send(text_data=json.dumps(payload))
            logger.debug(f"Sent initial snapshot for route {self.route_id} with {len(vehicles)} vehicles")
            
        except Exception as e:
            logger.exception(f"Error sending initial snapshot: {e}")
            await self.close(code=self.ERR_SERVER_ERROR)
