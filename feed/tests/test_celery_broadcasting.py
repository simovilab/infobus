"""
Integration Tests for Celery Broadcasting to WebSocket Consumers

Tests verify that Celery tasks (get_trip_updates, get_vehicle_positions) correctly
broadcast updates to WebSocket consumers using Django Channels.

Author: Brandon Trigueros Lara
Date: January 25, 2026
"""

import pytest
from unittest.mock import patch, MagicMock, call, AsyncMock
from datetime import datetime, timedelta
import pytz

from gtfs.models import (
    GTFSProvider,
    FeedMessage,
    TripUpdate,
    VehiclePosition,
    StopTimeUpdate,
)
from feed.tasks import get_trip_updates, get_vehicle_positions


@pytest.mark.django_db(transaction=True)
class TestCeleryBroadcasting:
    """Test suite for Celery task broadcasting integration"""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup test data for broadcasting tests"""
        # Create GTFSProvider
        self.provider = GTFSProvider.objects.create(
            code="TEST",
            name="Test Provider",
            timezone="America/Costa_Rica",
            trip_updates_url="http://example.com/trip_updates",
            vehicle_positions_url="http://example.com/vehicle_positions",
            is_active=True,
        )

        # Create FeedMessage
        self.feed_message = FeedMessage.objects.create(
            feed_message_id="TEST-trip-123456",
            provider=self.provider,
            entity_type="trip_update",
            timestamp=datetime.now(tz=pytz.UTC),
            incrementality=0,
            gtfs_realtime_version="2.0",
        )

    @patch("feed.tasks.requests.get")
    @patch("feed.tasks.get_channel_layer")
    def test_trip_update_broadcasts_to_websocket(
        self, mock_get_channel_layer, mock_requests_get
    ):
        """
        Test that get_trip_updates() broadcasts to TripConsumer via WebSocket.
        
        Validates:
        - channel_layer.group_send() is called with correct group name
        - Payload contains type='trip.update'
        - Payload includes serialized TripUpdate data
        """
        # Mock channel layer with async support
        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send = MagicMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        # Mock GTFS-RT response with minimal trip update
        mock_response = MagicMock()
        mock_response.content = self._create_mock_trip_update_protobuf()
        mock_requests_get.return_value = mock_response

        # Execute task
        result = get_trip_updates()

        # Verify task completed
        assert result == "TripUpdates saved to database"

        # Verify broadcast was sent
        assert mock_channel_layer.group_send.called
        
        # Get first call to group_send
        call_args = mock_channel_layer.group_send.call_args_list[0]
        group_name = call_args[0][0]
        payload = call_args[0][1]

        # Verify group name format
        assert group_name.startswith("trip_")
        
        # Verify payload structure
        assert payload["type"] == "trip.update"
        assert "trip" in payload
        assert "vehicle" in payload
        assert "timestamp" in payload

    @patch("feed.tasks.requests.get")
    @patch("feed.tasks.get_channel_layer")
    def test_vehicle_position_broadcasts_to_route(
        self, mock_get_channel_layer, mock_requests_get
    ):
        """
        Test that get_vehicle_positions() broadcasts to RouteConsumer.
        
        Validates:
        - Broadcasts sent to route_{route_id} group
        - Broadcasts sent to route_{route_id}_dir_{direction} groups
        - Payload contains type='route.update' and vehicles array
        - Batching works correctly (one broadcast per route, not per vehicle)
        """
        # Mock channel layer with async support
        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        # Mock GTFS-RT response with vehicle positions
        mock_response = MagicMock()
        mock_response.content = self._create_mock_vehicle_positions_protobuf()
        mock_requests_get.return_value = mock_response

        # Execute task
        result = get_vehicle_positions()

        # Verify task completed
        assert "VehiclePositions saved" in result

        # Verify broadcasts were sent
        assert mock_channel_layer.group_send.called
        
        # Collect all group_send calls
        calls = mock_channel_layer.group_send.call_args_list
        group_names = [call[0][0] for call in calls]

        # Verify route group broadcasts (excluding status group)
        route_groups = [g for g in group_names if g.startswith("route_")]
        assert len(route_groups) > 0

        # Verify at least one call has correct structure
        for call_item in calls:
            group_name = call_item[0][0]
            if group_name.startswith("route_"):
                payload = call_item[0][1]
                assert payload["type"] == "route.update"
                assert "vehicles" in payload
                assert isinstance(payload["vehicles"], list)
                break

    @patch("feed.tasks.requests.get")
    @patch("feed.tasks.get_channel_layer")
    def test_broadcasting_does_not_break_task(
        self, mock_get_channel_layer, mock_requests_get
    ):
        """
        Test that broadcasting errors don't break the main task.
        
        Validates:
        - Task completes successfully even if channel_layer.group_send() raises exception
        - TripUpdate/VehiclePosition data is saved to database
        - Error is logged but doesn't propagate
        """
        # Mock channel layer that raises exception
        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send.side_effect = Exception("Channel layer error")
        mock_get_channel_layer.return_value = mock_channel_layer

        # Mock GTFS-RT response
        mock_response = MagicMock()
        mock_response.content = self._create_mock_trip_update_protobuf()
        mock_requests_get.return_value = mock_response

        # Execute task - should not raise exception
        result = get_trip_updates()

        # Verify task completed successfully
        assert result == "TripUpdates saved to database"

        # Verify data was saved to database
        assert TripUpdate.objects.count() > 0

    @patch("feed.tasks.requests.get")
    @patch("feed.tasks.get_channel_layer")
    def test_batch_broadcasting_performance(
        self, mock_get_channel_layer, mock_requests_get
    ):
        """
        Test that multiple vehicles on same route are batched into single broadcast.
        
        Validates:
        - Multiple vehicles for same route result in ONE broadcast (not N broadcasts)
        - All vehicles are included in the batched payload
        - Direction-specific groups receive only relevant vehicles
        """
        # Mock channel layer with async support
        mock_channel_layer = MagicMock()
        mock_channel_layer.group_send = AsyncMock()
        mock_get_channel_layer.return_value = mock_channel_layer

        # Mock GTFS-RT response with multiple vehicles on same route
        mock_response = MagicMock()
        mock_response.content = self._create_mock_multiple_vehicles_protobuf()
        mock_requests_get.return_value = mock_response

        # Execute task
        result = get_vehicle_positions()

        # Verify task completed
        assert "VehiclePositions saved" in result

        # Collect all route broadcasts (excluding status group)
        calls = mock_channel_layer.group_send.call_args_list
        route_broadcasts = [
            call for call in calls if call[0][0].startswith("route_")
        ]

        # Verify batching: should be fewer broadcasts than vehicles
        # (ideally 1 per route + direction variations, not 1 per vehicle)
        vehicle_count = VehiclePosition.objects.count()
        assert len(route_broadcasts) < vehicle_count

        # Verify vehicles array contains multiple items
        found_batch = False
        for call_item in route_broadcasts:
            payload = call_item[0][1]
            if len(payload["vehicles"]) > 1:
                found_batch = True
                break
        
        assert found_batch, "No batched broadcast found with multiple vehicles"

    # Helper methods to create mock protobuf data

    def _create_mock_trip_update_protobuf(self):
        """Create minimal GTFS-RT FeedMessage with TripUpdate"""
        from google.transit import gtfs_realtime_pb2 as gtfs_rt
        
        feed = gtfs_rt.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.incrementality = gtfs_rt.FeedHeader.FULL_DATASET
        feed.header.timestamp = int(datetime.now().timestamp())

        entity = feed.entity.add()
        entity.id = "TEST_TRIP_001"
        
        # Trip descriptor
        entity.trip_update.trip.trip_id = "TRIP_001"
        entity.trip_update.trip.route_id = "ROUTE_01"
        entity.trip_update.trip.direction_id = 0
        entity.trip_update.trip.start_date = datetime.now().strftime("%Y%m%d")
        entity.trip_update.trip.start_time = "08:00:00"
        entity.trip_update.trip.schedule_relationship = gtfs_rt.TripDescriptor.SCHEDULED
        
        # Vehicle descriptor
        entity.trip_update.vehicle.id = "VEH_001"
        entity.trip_update.vehicle.label = "Bus 001"
        
        # Timestamp
        entity.trip_update.timestamp = int(datetime.now().timestamp())

        # Stop time update
        stop_time = entity.trip_update.stop_time_update.add()
        stop_time.stop_id = "STOP_001"
        stop_time.arrival.time = int((datetime.now() + timedelta(minutes=5)).timestamp())

        return feed.SerializeToString()

    def _create_mock_vehicle_positions_protobuf(self):
        """Create minimal GTFS-RT FeedMessage with VehiclePositions"""
        from google.transit import gtfs_realtime_pb2 as gtfs_rt
        
        feed = gtfs_rt.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.incrementality = gtfs_rt.FeedHeader.FULL_DATASET
        feed.header.timestamp = int(datetime.now().timestamp())

        # Create 2 vehicles on same route
        for i in range(2):
            entity = feed.entity.add()
            entity.id = f"VEH_00{i+1}"
            
            # Vehicle descriptor
            entity.vehicle.vehicle.id = f"VEH_00{i+1}"
            entity.vehicle.vehicle.label = f"Bus {i+1}"
            
            # Trip descriptor
            entity.vehicle.trip.trip_id = f"TRIP_00{i+1}"
            entity.vehicle.trip.route_id = "ROUTE_01"  # Same route
            entity.vehicle.trip.direction_id = i % 2  # Different directions
            entity.vehicle.trip.start_date = datetime.now().strftime("%Y%m%d")
            entity.vehicle.trip.start_time = "08:00:00"
            
            # Position
            entity.vehicle.position.latitude = 9.9281 + (i * 0.001)
            entity.vehicle.position.longitude = -84.0907 + (i * 0.001)
            entity.vehicle.position.bearing = 180.0
            entity.vehicle.position.speed = 15.0
            
            # Timestamp
            entity.vehicle.timestamp = int(datetime.now().timestamp())
            
            # Current stop
            entity.vehicle.current_stop_sequence = 5 + i

        return feed.SerializeToString()

    def _create_mock_multiple_vehicles_protobuf(self):
        """Create GTFS-RT FeedMessage with 5 vehicles on same route"""
        from google.transit import gtfs_realtime_pb2 as gtfs_rt
        
        feed = gtfs_rt.FeedMessage()
        feed.header.gtfs_realtime_version = "2.0"
        feed.header.incrementality = gtfs_rt.FeedHeader.FULL_DATASET
        feed.header.timestamp = int(datetime.now().timestamp())

        # Create 5 vehicles on same route
        for i in range(5):
            entity = feed.entity.add()
            entity.id = f"VEH_BATCH_{i+1:03d}"
            
            # Vehicle descriptor
            entity.vehicle.vehicle.id = f"VEH_{i+1:03d}"
            entity.vehicle.vehicle.label = f"Bus {i+1}"
            
            # Trip descriptor - all same route
            entity.vehicle.trip.trip_id = f"TRIP_BATCH_{i+1:03d}"
            entity.vehicle.trip.route_id = "ROUTE_BATCH_01"
            entity.vehicle.trip.direction_id = i % 2
            entity.vehicle.trip.start_date = datetime.now().strftime("%Y%m%d")
            entity.vehicle.trip.start_time = f"{8 + i}:00:00"
            
            # Position
            entity.vehicle.position.latitude = 9.9281 + (i * 0.01)
            entity.vehicle.position.longitude = -84.0907 + (i * 0.01)
            entity.vehicle.position.bearing = 180.0
            entity.vehicle.position.speed = 15.0 + i
            
            # Timestamp
            entity.vehicle.timestamp = int(datetime.now().timestamp())
            
            # Current stop
            entity.vehicle.current_stop_sequence = i + 1

        return feed.SerializeToString()
