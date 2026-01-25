"""
WebSocket Consumer for GTFS-Realtime Trip Updates.

Handles real-time updates for a specific trip, broadcasting position
and stop time updates to subscribed clients.

Example Usage:
    URL: ws://localhost:8000/ws/trips/12345?include_stops=true&include_shape=false
    
    Client receives:
    {
        "trip_id": "12345",
        "route_id": "100",
        "direction_id": 1,
        "vehicle": {
            "vehicle_id": "BUS_001",
            "label": "101",
            "position": {"latitude": 9.9355, "longitude": -84.0795}
        },
        "stop_time_updates": [...],
        "timestamp": "2026-01-24T02:15:00Z"
    }
"""

import json
import logging
from typing import Optional
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.exceptions import ObjectDoesNotExist

from gtfs.models import TripUpdate
from websocket.serializers.gtfs import serialize_trip_update

logger = logging.getLogger(__name__)


class TripConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time trip updates.
    
    Clients connect to /ws/trips/{trip_id} and receive updates whenever
    the vehicle position or stop times change.
    
    Error Codes:
        4001: Trip not found in database
        4002: Invalid query parameters
        5001: Internal server error
    """
    
    # Error codes (AsyncAPI compliant)
    ERR_TRIP_NOT_FOUND = 4001
    ERR_INVALID_PARAMS = 4002
    ERR_SERVER_ERROR = 5001
    
    async def connect(self):
        """
        Accept WebSocket connection and subscribe to trip updates.
        
        Validates trip exists, parses query parameters, adds client to
        channel group, and sends initial snapshot.
        """
        try:
            # Extract trip_id from URL path
            self.trip_id = self.scope['url_route']['kwargs']['trip_id']
            
            # Parse query parameters
            self.parse_query_params()
            
            # Validate trip exists in database
            if not await self.trip_exists():
                logger.warning(f"Trip not found: {self.trip_id}")
                await self.close(code=self.ERR_TRIP_NOT_FOUND)
                return
            
            # Add to channel layer group
            self.group_name = f"trip_{self.trip_id}"
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            # Accept connection
            await self.accept()
            logger.info(f"Client connected to trip {self.trip_id}")
            
            # Send initial snapshot
            await self.send_initial_snapshot()
            
        except ValueError as e:
            logger.error(f"Invalid parameters: {e}")
            await self.close(code=self.ERR_INVALID_PARAMS)
        except Exception as e:
            trip_id = getattr(self, 'trip_id', 'unknown')
            logger.exception(f"Error connecting to trip {trip_id}: {e}")
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
            logger.info(f"Client disconnected from trip {self.trip_id} (code: {close_code})")
    
    async def trip_update(self, event):
        """
        Receive broadcast from Celery task and forward to client.
        
        Called when channel_layer.group_send() is invoked with type='trip.update'.
        
        Event structure:
            {
                "type": "trip.update",
                "trip_id": "12345",
                "data": {...}  # Optional pre-serialized payload
            }
        
        Args:
            event: Event dict from channel layer
        """
        try:
            trip_id = event.get('trip_id')
            
            # Verify this update is for our trip
            if trip_id != self.trip_id:
                return
            
            # Use pre-serialized data if available, otherwise query and serialize
            if 'data' in event:
                payload = event['data']
            else:
                trip_update = await self.get_trip_update()
                payload = serialize_trip_update(
                    trip_update,
                    include_stops=self.include_stops
                )
            
            # Add message type
            payload['type'] = 'trip.update'
            
            # Send JSON to client
            await self.send(text_data=json.dumps(payload))
            logger.debug(f"Sent update for trip {self.trip_id}")
            
        except ObjectDoesNotExist:
            logger.error(f"Trip {self.trip_id} no longer exists")
            await self.close(code=self.ERR_TRIP_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error sending trip update: {e}")
            # Don't close connection on serialization errors, just log
    
    def parse_query_params(self):
        """
        Parse and validate query parameters from URL.
        
        Extracts:
            - include_stops: bool (default: True)
            - include_shape: bool (default: False)
        
        Raises:
            ValueError: If parameters are invalid
        """
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        params = parse_qs(query_string)
        
        # Parse include_stops (default: True)
        include_stops_str = params.get('include_stops', ['true'])[0].lower()
        if include_stops_str not in ('true', 'false', '1', '0'):
            raise ValueError(f"Invalid include_stops value: {include_stops_str}")
        self.include_stops = include_stops_str in ('true', '1')
        
        # Parse include_shape (default: False)
        include_shape_str = params.get('include_shape', ['false'])[0].lower()
        if include_shape_str not in ('true', 'false', '1', '0'):
            raise ValueError(f"Invalid include_shape value: {include_shape_str}")
        self.include_shape = include_shape_str in ('true', '1')
        
        logger.debug(f"Query params: include_stops={self.include_stops}, include_shape={self.include_shape}")
    
    @database_sync_to_async
    def trip_exists(self) -> bool:
        """
        Check if trip exists in database.
        
        Returns:
            bool: True if trip exists, False otherwise
        """
        return TripUpdate.objects.filter(trip_trip_id=self.trip_id).exists()
    
    @database_sync_to_async
    def get_trip_update(self) -> TripUpdate:
        """
        Fetch TripUpdate from database with related data.
        
        Uses select_related and prefetch_related for optimal performance.
        
        Returns:
            TripUpdate: Trip update object with relations loaded
        
        Raises:
            ObjectDoesNotExist: If trip no longer exists
        """
        return TripUpdate.objects.select_related(
            'feed_message'
        ).prefetch_related(
            'stoptimeupdate_set'
        ).filter(trip_trip_id=self.trip_id).order_by('-timestamp').first()
    
    async def send_initial_snapshot(self):
        """
        Send current state of trip to newly connected client.
        
        Fetches latest data from database and sends as initial message.
        """
        try:
            trip_update = await self.get_trip_update()
            payload = serialize_trip_update(
                trip_update,
                include_stops=self.include_stops
            )
            payload['type'] = 'trip.snapshot'
            await self.send(text_data=json.dumps(payload))
            logger.debug(f"Sent initial snapshot for trip {self.trip_id}")
        except ObjectDoesNotExist:
            logger.error(f"Trip {self.trip_id} disappeared after connection")
            await self.close(code=self.ERR_TRIP_NOT_FOUND)
        except Exception as e:
            logger.exception(f"Error sending initial snapshot: {e}")
            await self.close(code=self.ERR_SERVER_ERROR)
