"""
Unit tests for WebSocket consumers.

Tests TripConsumer using simple fixtures that match actual database schema.
"""

import asyncio
import pytest
import pytest_asyncio
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from channels.routing import URLRouter
from django.urls import re_path
from django.utils import timezone
from asgiref.sync import sync_to_async

from gtfs.models import TripUpdate, FeedMessage, GTFSProvider
from websocket.consumers.trip import TripConsumer


# Configure database access for all tests
pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.asyncio]


# Async fixtures
@pytest_asyncio.fixture
async def provider(db):
    """Create test provider (async)."""
    @sync_to_async
    def create():
        return GTFSProvider.objects.create(code='TEST', name='Test Provider')
    return await create()


@pytest_asyncio.fixture
async def feed_msg(db, provider):
    """Create test feed message (async)."""
    @sync_to_async
    def create():
        return FeedMessage.objects.create(
            feed_message_id='TEST_001',
            provider=provider,
            entity_type='trip_update',
            incrementality='FULL_DATASET',
            gtfs_realtime_version='2.0'
        )
    return await create()


@pytest_asyncio.fixture
async def trip_update(db, feed_msg):
    """Create test trip update (async)."""
    @sync_to_async
    def create():
        return TripUpdate.objects.create(
            entity_id='TEST_ENTITY',
            feed_message=feed_msg,
            trip_trip_id='TRIP_001',
            trip_route_id='ROUTE_100',
            trip_direction_id=1,
            vehicle_id='BUS_001',
            vehicle_label='101',
            timestamp=timezone.now()
        )
    return await create()


# Create application with URL routing
application = URLRouter([
    re_path(r'ws/trips/(?P<trip_id>[^/]+)/$', TripConsumer.as_asgi()),
])


class TestTripConsumerBasic:
    """Basic consumer tests."""
    
    async def test_connect_valid_trip(self, trip_update):
        """Should accept connection for existing trip."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/trips/{trip_update.trip_trip_id}/"
        )
        connected, _ = await communicator.connect()
        assert connected, "Connection should succeed for valid trip"
        
        response = await communicator.receive_json_from(timeout=5)
        assert 'trip' in response, "Response should contain 'trip' field"
        assert response['trip']['trip_id'] == trip_update.trip_trip_id
        
        await communicator.disconnect()
    
    async def test_connect_invalid_trip(self):
        """Should reject non-existent trip with 4001."""
        communicator = WebsocketCommunicator(
            application,
            "/ws/trips/INVALID/"
        )
        connected, code = await communicator.connect()
        assert not connected, "Should reject invalid trip"
        assert code == 4001, f"Expected error code 4001, got {code}"
    
    async def test_query_params(self, trip_update):
        """Should parse query parameters."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/trips/{trip_update.trip_trip_id}/?include_stops=false"
        )
        connected, _ = await communicator.connect()
        assert connected, "Connection should succeed with query params"
        await communicator.receive_json_from(timeout=5)
        await communicator.disconnect()
    
    async def test_invalid_params(self, trip_update):
        """Should reject invalid parameters with 4002."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/trips/{trip_update.trip_trip_id}/?include_stops=invalid"
        )
        connected, code = await communicator.connect()
        assert not connected, "Should reject invalid params"
        assert code == 4002, f"Expected error code 4002, got {code}"


class TestTripConsumerBroadcast:
    """Broadcast message tests."""
    
    async def test_receive_broadcast(self, trip_update):
        """Should receive and forward broadcasts."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/trips/{trip_update.trip_trip_id}/"
        )
        
        connected, _ = await communicator.connect()
        assert connected, "Connection should succeed"
        await communicator.receive_json_from(timeout=5)  # Initial snapshot
        
        # Send broadcast
        channel_layer = get_channel_layer()
        test_data = {
            "trip": {"trip_id": trip_update.trip_trip_id, "route_id": "ROUTE_100"},
            "timestamp": "2026-01-24T00:00:00Z"
        }
        await channel_layer.group_send(
            f"trip_{trip_update.trip_trip_id}",
            {"type": "trip.update", "trip_id": trip_update.trip_trip_id, "data": test_data}
        )
        
        response = await communicator.receive_json_from(timeout=5)
        assert response['trip']['trip_id'] == trip_update.trip_trip_id
        
        await communicator.disconnect()
    
    async def test_ignore_other_trips(self, trip_update):
        """Should ignore broadcasts for other trips."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/trips/{trip_update.trip_trip_id}/"
        )
        
        connected, _ = await communicator.connect()
        assert connected, "Connection should succeed"
        await communicator.receive_json_from(timeout=5)
        
        # Send broadcast for different trip
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"trip_{trip_update.trip_trip_id}",
            {"type": "trip.update", "trip_id": "OTHER_TRIP", "data": {}}
        )
        
        # Should timeout waiting since different trip ID
        with pytest.raises(asyncio.TimeoutError):
            await communicator.receive_json_from(timeout=1)
        
        # Cleanup - ignore errors from disconnecting
        try:
            await communicator.disconnect()
        except asyncio.CancelledError:
            pass
