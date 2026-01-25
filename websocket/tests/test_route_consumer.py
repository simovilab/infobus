"""
Unit tests for RouteConsumer.

Tests WebSocket consumer for route-level vehicle updates with direction filtering.
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
from datetime import timedelta

from gtfs.models import Route, VehiclePosition, FeedMessage, GTFSProvider, Feed, Agency
from websocket.consumers.route import RouteConsumer


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
            entity_type='vehicle_position',
            incrementality='FULL_DATASET',
            gtfs_realtime_version='2.0'
        )
    return await create()


@pytest_asyncio.fixture
async def feed(db, provider):
    """Create test GTFS feed (async)."""
    @sync_to_async
    def create():
        return Feed.objects.create(
            feed_id='TEST_FEED',
            gtfs_provider=provider
        )
    return await create()


@pytest_asyncio.fixture
async def agency(db, feed):
    """Create test GTFS agency (async)."""
    @sync_to_async
    def create():
        return Agency.objects.create(
            feed=feed,
            agency_id='TEST_AGENCY',
            agency_name='Test Agency',
            agency_url='https://example.com',
            agency_timezone='America/Costa_Rica'
        )
    return await create()


@pytest_asyncio.fixture
async def route(db, feed, agency):
    """Create test route in GTFS Schedule (async)."""
    @sync_to_async
    def create():
        return Route.objects.create(
            feed=feed,
            route_id='ROUTE_001',
            agency_id=agency.agency_id,
            route_short_name='R01',
            route_long_name='Test Route 001',
            route_type=3  # Bus
        )
    return await create()


@pytest_asyncio.fixture
async def vehicle_position_dir0(db, feed_msg, route):
    """Create test vehicle position for direction 0 (async)."""
    @sync_to_async
    def create():
        return VehiclePosition.objects.create(
            entity_id='TEST_VP_001',
            feed_message=feed_msg,
            vehicle_trip_route_id=route.route_id,
            vehicle_trip_trip_id='TRIP_001',
            vehicle_trip_direction_id=0,
            vehicle_vehicle_id='BUS_001',
            vehicle_vehicle_label='101',
            vehicle_position_latitude=9.9355,
            vehicle_position_longitude=-84.0795,
            vehicle_position_bearing=45.0,
            vehicle_position_speed=30.0,
            vehicle_timestamp=timezone.now()
        )
    return await create()


@pytest_asyncio.fixture
async def vehicle_position_dir1(db, feed_msg, route):
    """Create test vehicle position for direction 1 (async)."""
    @sync_to_async
    def create():
        return VehiclePosition.objects.create(
            entity_id='TEST_VP_002',
            feed_message=feed_msg,
            vehicle_trip_route_id=route.route_id,
            vehicle_trip_trip_id='TRIP_002',
            vehicle_trip_direction_id=1,
            vehicle_vehicle_id='BUS_002',
            vehicle_vehicle_label='102',
            vehicle_position_latitude=9.9400,
            vehicle_position_longitude=-84.0800,
            vehicle_position_bearing=135.0,
            vehicle_position_speed=25.0,
            vehicle_timestamp=timezone.now()
        )
    return await create()


# Create application with URL routing
application = URLRouter([
    re_path(r'ws/route/(?P<route_id>[^/]+)/$', RouteConsumer.as_asgi()),
    re_path(r'ws/route/(?P<route_id>[^/]+)/direction/(?P<direction_id>[01])/$', RouteConsumer.as_asgi()),
])


class TestRouteConsumerConnection:
    """Test connection handling."""
    
    async def test_connect_success_all_directions(self, route, vehicle_position_dir0, vehicle_position_dir1):
        """Should accept connection for existing route without direction filter."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/route/{route.route_id}/"
        )
        connected, _ = await communicator.connect()
        assert connected, "Connection should succeed for valid route"
        
        # Should receive snapshot with both vehicles
        response = await communicator.receive_json_from(timeout=5)
        assert response['type'] == 'route.snapshot', f"Expected 'route.snapshot', got {response.get('type')}"
        assert response['route_id'] == route.route_id
        assert 'vehicles' in response
        assert response['count'] >= 2, "Should include vehicles from both directions"
        
        await communicator.disconnect()
    
    async def test_connect_success_specific_direction(self, route, vehicle_position_dir0, vehicle_position_dir1):
        """Should accept connection with direction filter and only return matching vehicles."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/route/{route.route_id}/direction/0/"
        )
        connected, _ = await communicator.connect()
        assert connected, "Connection should succeed for valid route with direction"
        
        # Should receive snapshot with only direction 0 vehicles
        response = await communicator.receive_json_from(timeout=5)
        assert response['type'] == 'route.snapshot'
        assert response['route_id'] == route.route_id
        assert response['direction_id'] == 0
        assert 'vehicles' in response
        
        # Verify all vehicles have direction_id = 0
        for vehicle in response['vehicles']:
            assert vehicle['trip']['direction_id'] == 0, "All vehicles should be direction 0"
        
        await communicator.disconnect()
    
    async def test_connect_route_not_found(self):
        """Should reject connection for non-existent route with code 4004."""
        communicator = WebsocketCommunicator(
            application,
            "/ws/route/INVALID_ROUTE/"
        )
        connected, code = await communicator.connect()
        assert not connected, "Should reject invalid route"
        assert code == 4004, f"Expected error code 4004 (route not found), got {code}"
    
    async def test_connect_invalid_direction(self, route):
        """Should reject connection with invalid direction_id (not 0 or 1)."""
        # The URL pattern only accepts [01], so direction 5 won't match the route
        # This will fail at routing level, not at consumer level
        # Test that the URL pattern properly rejects invalid directions
        communicator = WebsocketCommunicator(
            application,
            f"/ws/route/{route.route_id}/direction/2/"  # Invalid - only 0 or 1 allowed
        )
        
        # This should timeout or fail to connect because URL doesn't match pattern
        try:
            connected, code = await communicator.connect(timeout=2)
            # If it somehow connects (shouldn't), verify it closes with error
            if connected:
                await communicator.disconnect()
                assert False, "Should not connect with invalid direction"
        except (ValueError, asyncio.TimeoutError):
            # Expected - URL doesn't match pattern
            pass


class TestRouteConsumerBroadcast:
    """Test broadcast functionality."""
    
    async def test_route_update_broadcast(self, route, vehicle_position_dir0):
        """Should receive broadcast updates for subscribed route."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/route/{route.route_id}/"
        )
        connected, _ = await communicator.connect()
        assert connected
        
        # Consume initial snapshot
        await communicator.receive_json_from(timeout=5)
        
        # Send broadcast via channel layer
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"route_{route.route_id}",
            {
                "type": "route.update",
                "route_id": route.route_id
            }
        )
        
        # Should receive update
        response = await communicator.receive_json_from(timeout=5)
        assert response['type'] == 'route.update'
        assert response['route_id'] == route.route_id
        assert 'vehicles' in response
        
        await communicator.disconnect()
    
    async def test_route_update_wrong_route(self, route, vehicle_position_dir0):
        """Should not receive broadcasts for different route."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/route/{route.route_id}/"
        )
        connected, _ = await communicator.connect()
        assert connected
        
        # Consume initial snapshot
        await communicator.receive_json_from(timeout=5)
        
        # Send broadcast for different route
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "route_OTHER_ROUTE",
            {
                "type": "route.update",
                "route_id": "OTHER_ROUTE"
            }
        )
        
        # Should timeout (no message received)
        with pytest.raises(asyncio.TimeoutError):
            await communicator.receive_json_from(timeout=2)
        
        # Cleanup
        try:
            await communicator.disconnect()
        except:
            pass  # Ignore disconnect errors
    
    async def test_direction_filtering(self, route, vehicle_position_dir0, vehicle_position_dir1):
        """Should filter broadcasts by direction when subscribed to specific direction."""
        # Connect to direction 0 only
        communicator = WebsocketCommunicator(
            application,
            f"/ws/route/{route.route_id}/direction/0/"
        )
        connected, _ = await communicator.connect()
        assert connected
        
        # Consume initial snapshot
        snapshot = await communicator.receive_json_from(timeout=5)
        assert snapshot['direction_id'] == 0
        
        # Send broadcast with direction_id = 1
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"route_{route.route_id}_dir_0",
            {
                "type": "route.update",
                "route_id": route.route_id,
                "direction_id": 1  # Different direction
            }
        )
        
        # Should timeout because direction doesn't match
        with pytest.raises(asyncio.TimeoutError):
            await communicator.receive_json_from(timeout=2)
        
        # Cleanup
        try:
            await communicator.disconnect()
        except:
            pass  # Ignore disconnect errors


class TestRouteConsumerEdgeCases:
    """Test edge cases and error handling."""
    
    async def test_empty_route(self, route):
        """Should handle route with no active vehicles gracefully."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/route/{route.route_id}/"
        )
        connected, _ = await communicator.connect()
        assert connected
        
        # Should receive snapshot with empty vehicles array
        response = await communicator.receive_json_from(timeout=5)
        assert response['type'] == 'route.snapshot'
        assert response['count'] == 0
        assert response['vehicles'] == []
        
        await communicator.disconnect()
    
    async def test_snapshot_format(self, route, vehicle_position_dir0):
        """Should return correctly formatted snapshot according to AsyncAPI spec."""
        communicator = WebsocketCommunicator(
            application,
            f"/ws/route/{route.route_id}/"
        )
        connected, _ = await communicator.connect()
        assert connected
        
        response = await communicator.receive_json_from(timeout=5)
        
        # Verify required fields exist
        assert 'type' in response
        assert 'route_id' in response
        assert 'timestamp' in response
        assert 'count' in response
        assert 'vehicles' in response
        
        # Verify vehicle structure if vehicles exist
        if response['count'] > 0:
            vehicle = response['vehicles'][0]
            assert 'trip' in vehicle
            assert 'vehicle' in vehicle
            assert 'position' in vehicle
            assert 'timestamp' in vehicle
            
            # Verify nested structures
            assert 'trip_id' in vehicle['trip']
            assert 'route_id' in vehicle['trip']
            assert 'direction_id' in vehicle['trip']
            
            assert 'id' in vehicle['vehicle']
            assert 'label' in vehicle['vehicle']
            
            assert 'latitude' in vehicle['position']
            assert 'longitude' in vehicle['position']
        
        await communicator.disconnect()
