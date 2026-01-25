"""
Unit Tests for GTFS-Realtime Serializers

Tests serialization functions that convert Django models to AsyncAPI-compliant JSON.

Test Coverage:
- serialize_trip_update() with various scenarios
- serialize_vehicle_position()  
- serialize_stop_time_update()
- serialize_route_vehicles() with direction filtering

Author: Brandon Trigueros Lara
Date: January 23, 2026
"""

import pytest
from datetime import datetime, date, timedelta
from django.utils import timezone
import pytz

from gtfs.models import (
    TripUpdate,
    VehiclePosition,
    StopTimeUpdate,
    FeedMessage,
    GTFSProvider,
)
from websocket.serializers.gtfs import (
    serialize_trip_update,
    serialize_vehicle_position,
    serialize_stop_time_update,
    serialize_route_vehicles,
)


# Fixtures for test data
@pytest.fixture
def gtfs_provider(db):
    """Create a test GTFS provider."""
    return GTFSProvider.objects.create(
        code="TEST",
        name="Test Transit",
        timezone="America/Costa_Rica",
        is_active=True,
    )


@pytest.fixture
def feed_message(db, gtfs_provider):
    """Create a test feed message."""
    return FeedMessage.objects.create(
        feed_message_id="TEST-trip-1234567890",
        provider=gtfs_provider,
        entity_type="trip_update",
        timestamp=timezone.now(),
        incrementality=0,
        gtfs_realtime_version="2.0",
    )


@pytest.fixture
def trip_update(db, feed_message):
    """Create a test trip update."""
    return TripUpdate.objects.create(
        entity_id="TRIP_001",
        feed_message=feed_message,
        trip_trip_id="CR-SJ-01-123",
        trip_route_id="ROUTE_001",
        trip_direction_id=0,
        trip_start_time=timedelta(hours=8, minutes=30),
        trip_start_date=date.today(),
        trip_schedule_relationship="SCHEDULED",
        vehicle_id="VEH_001",
        vehicle_label="Bus 101",
        vehicle_license_plate="ABC-123",
        timestamp=timezone.now(),
        delay=120,  # 2 minutes delay
    )


@pytest.fixture
def vehicle_position(db, feed_message):
    """Create a test vehicle position."""
    return VehiclePosition.objects.create(
        entity_id="VEH_POS_001",
        feed_message=feed_message,
        vehicle_trip_trip_id="CR-SJ-01-123",
        vehicle_trip_route_id="ROUTE_001",
        vehicle_trip_direction_id=0,
        vehicle_trip_start_date=date.today(),
        vehicle_vehicle_id="VEH_001",
        vehicle_vehicle_label="Bus 101",
        vehicle_position_latitude=9.9281,
        vehicle_position_longitude=-84.0907,
        vehicle_position_bearing=180.5,
        vehicle_position_speed=12.5,
        vehicle_current_status="IN_TRANSIT_TO",
        vehicle_timestamp=timezone.now(),
        vehicle_congestion_level="RUNNING_SMOOTHLY",
    )


@pytest.fixture
def stop_time_update(db, feed_message, trip_update):
    """Create a test stop time update."""
    return StopTimeUpdate.objects.create(
        feed_message=feed_message,
        trip_update=trip_update,
        stop_sequence=5,
        stop_id="STOP_123",
        arrival_delay=60,
        arrival_time=timezone.now() + timedelta(minutes=5),
        departure_delay=90,
        departure_time=timezone.now() + timedelta(minutes=6),
        schedule_relationship="SCHEDULED",
    )


# Tests for serialize_trip_update()
@pytest.mark.django_db
class TestSerializeTripUpdate:
    """Test cases for trip update serialization."""

    def test_serialize_trip_update_basic(self, trip_update):
        """Test basic trip update serialization."""
        result = serialize_trip_update(trip_update, include_stops=False)

        assert result["trip"]["trip_id"] == "CR-SJ-01-123"
        assert result["trip"]["route_id"] == "ROUTE_001"
        assert result["trip"]["direction_id"] == 0
        assert result["trip"]["schedule_relationship"] == "SCHEDULED"
        assert result["vehicle"]["id"] == "VEH_001"
        assert result["vehicle"]["label"] == "Bus 101"
        assert result["delay"] == 120
        assert result["timestamp"] is not None

    def test_serialize_trip_update_with_vehicle_position(
        self, trip_update, vehicle_position
    ):
        """Test trip update includes vehicle position when available."""
        result = serialize_trip_update(trip_update, include_stops=False)

        assert "position" in result["vehicle"]
        assert result["vehicle"]["position"]["latitude"] == 9.9281
        assert result["vehicle"]["position"]["longitude"] == -84.0907
        assert result["vehicle"]["position"]["bearing"] == 180.5
        assert result["vehicle"]["position"]["speed"] == 12.5
        assert result["vehicle"]["current_status"] == "IN_TRANSIT_TO"
        assert result["vehicle"]["congestion_level"] == "RUNNING_SMOOTHLY"

    def test_serialize_trip_update_with_stops(self, trip_update, stop_time_update):
        """Test trip update includes stop time updates when requested."""
        result = serialize_trip_update(trip_update, include_stops=True)

        assert "stop_time_updates" in result
        assert len(result["stop_time_updates"]) == 1
        assert result["stop_time_updates"][0]["stop_id"] == "STOP_123"
        assert result["stop_time_updates"][0]["stop_sequence"] == 5

    def test_serialize_trip_update_without_stops(self, trip_update):
        """Test trip update excludes stops when not requested."""
        result = serialize_trip_update(trip_update, include_stops=False)

        assert "stop_time_updates" in result
        assert len(result["stop_time_updates"]) == 0

    def test_serialize_trip_update_no_vehicle_position(self, trip_update):
        """Test trip update without associated vehicle position."""
        result = serialize_trip_update(trip_update, include_stops=False)

        # Should have vehicle descriptor but no position
        assert result["vehicle"]["id"] == "VEH_001"
        assert "position" not in result["vehicle"] or result["vehicle"]["position"] is None

    def test_serialize_trip_update_schema_compliance(self, trip_update):
        """Test that serialized output follows AsyncAPI schema structure."""
        result = serialize_trip_update(trip_update, include_stops=False)

        # Verify required top-level keys
        required_keys = ["trip", "vehicle", "timestamp", "delay", "stop_time_updates"]
        for key in required_keys:
            assert key in result, f"Missing required key: {key}"

        # Verify trip structure
        trip_keys = ["trip_id", "route_id", "direction_id"]
        for key in trip_keys:
            assert key in result["trip"], f"Missing trip key: {key}"

        # Verify vehicle structure
        vehicle_keys = ["id", "label"]
        for key in vehicle_keys:
            assert key in result["vehicle"], f"Missing vehicle key: {key}"


# Tests for serialize_vehicle_position()
@pytest.mark.django_db
class TestSerializeVehiclePosition:
    """Test cases for vehicle position serialization."""

    def test_serialize_vehicle_position_complete(self, vehicle_position):
        """Test serialization with all fields populated."""
        result = serialize_vehicle_position(vehicle_position)

        assert result["trip"]["trip_id"] == "CR-SJ-01-123"
        assert result["trip"]["route_id"] == "ROUTE_001"
        assert result["vehicle"]["id"] == "VEH_001"
        assert result["vehicle"]["label"] == "Bus 101"
        assert result["position"]["latitude"] == 9.9281
        assert result["position"]["longitude"] == -84.0907
        assert result["position"]["bearing"] == 180.5
        assert result["position"]["speed"] == 12.5
        assert result["current_status"] == "IN_TRANSIT_TO"
        assert result["congestion_level"] == "RUNNING_SMOOTHLY"

    def test_serialize_vehicle_position_minimal(self, feed_message):
        """Test serialization with minimal required fields."""
        vp = VehiclePosition.objects.create(
            entity_id="VEH_MIN",
            feed_message=feed_message,
            vehicle_trip_trip_id="TRIP_MIN",
            vehicle_position_latitude=10.0,
            vehicle_position_longitude=-85.0,
        )

        result = serialize_vehicle_position(vp)

        assert result["trip"]["trip_id"] == "TRIP_MIN"
        assert result["position"]["latitude"] == 10.0
        assert result["position"]["longitude"] == -85.0
        # Defaults should be applied
        assert result["current_status"] == "IN_TRANSIT_TO"

    def test_serialize_vehicle_position_timestamp_format(self, vehicle_position):
        """Test that timestamp is properly formatted as ISO 8601."""
        result = serialize_vehicle_position(vehicle_position)

        assert "timestamp" in result
        # Should be ISO 8601 format
        datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))

    def test_serialize_vehicle_position_geometry_conversion(self, vehicle_position):
        """Test conversion from Point geometry to lat/lon coordinates."""
        result = serialize_vehicle_position(vehicle_position)

        # Verify coordinates are floats
        assert isinstance(result["position"]["latitude"], float)
        assert isinstance(result["position"]["longitude"], float)
        # Verify reasonable values for Costa Rica
        assert -90 <= result["position"]["latitude"] <= 90
        assert -180 <= result["position"]["longitude"] <= 180


# Tests for serialize_stop_time_update()
@pytest.mark.django_db
class TestSerializeStopTimeUpdate:
    """Test cases for stop time update serialization."""

    def test_serialize_stop_time_update_with_delays(self, stop_time_update):
        """Test serialization with arrival and departure delays."""
        result = serialize_stop_time_update(stop_time_update)

        assert result["stop_sequence"] == 5
        assert result["stop_id"] == "STOP_123"
        assert result["schedule_relationship"] == "SCHEDULED"
        assert "arrival" in result
        assert result["arrival"]["delay"] == 60
        assert "departure" in result
        assert result["departure"]["delay"] == 90

    def test_serialize_stop_time_update_no_delays(self, feed_message, trip_update):
        """Test serialization without delays (on-time)."""
        stu = StopTimeUpdate.objects.create(
            feed_message=feed_message,
            trip_update=trip_update,
            stop_sequence=1,
            stop_id="STOP_001",
            arrival_delay=0,
            arrival_time=timezone.now(),
            departure_delay=0,
            departure_time=timezone.now(),
        )

        result = serialize_stop_time_update(stu)

        assert result["arrival"]["delay"] == 0
        assert result["departure"]["delay"] == 0

    def test_serialize_stop_time_update_time_format(self, stop_time_update):
        """Test that times are formatted as ISO 8601."""
        result = serialize_stop_time_update(stop_time_update)

        if result["arrival"]["time"]:
            datetime.fromisoformat(result["arrival"]["time"].replace("Z", "+00:00"))
        if result["departure"]["time"]:
            datetime.fromisoformat(result["departure"]["time"].replace("Z", "+00:00"))


# Tests for serialize_route_vehicles()
@pytest.mark.django_db
class TestSerializeRouteVehicles:
    """Test cases for route vehicles snapshot serialization."""

    def test_serialize_route_vehicles_both_directions(
        self, vehicle_position, feed_message
    ):
        """Test route snapshot with vehicles in both directions."""
        # Create vehicle in opposite direction
        VehiclePosition.objects.create(
            entity_id="VEH_002",
            feed_message=feed_message,
            vehicle_trip_trip_id="CR-SJ-01-456",
            vehicle_trip_route_id="ROUTE_001",
            vehicle_trip_direction_id=1,  # Opposite direction
            vehicle_vehicle_id="VEH_002",
            vehicle_position_latitude=9.93,
            vehicle_position_longitude=-84.09,
            vehicle_timestamp=timezone.now(),
        )

        result = serialize_route_vehicles("ROUTE_001", direction_id=None)

        assert result["route_id"] == "ROUTE_001"
        assert result["direction_id"] is None
        assert result["count"] == 2
        assert len(result["vehicles"]) == 2

    def test_serialize_route_vehicles_single_direction(self, vehicle_position):
        """Test route snapshot filtered by direction."""
        result = serialize_route_vehicles("ROUTE_001", direction_id=0)

        assert result["route_id"] == "ROUTE_001"
        assert result["direction_id"] == 0
        assert result["count"] == 1
        assert len(result["vehicles"]) == 1
        assert result["vehicles"][0]["trip"]["direction_id"] == 0

    def test_serialize_route_vehicles_empty(self):
        """Test route with no active vehicles."""
        result = serialize_route_vehicles("ROUTE_EMPTY")

        assert result["route_id"] == "ROUTE_EMPTY"
        assert result["count"] == 0
        assert len(result["vehicles"]) == 0

    def test_serialize_route_vehicles_count_accuracy(
        self, vehicle_position, feed_message
    ):
        """Test that count field matches actual vehicles array length."""
        # Create additional vehicles
        for i in range(3):
            VehiclePosition.objects.create(
                entity_id=f"VEH_{i+2}",
                feed_message=feed_message,
                vehicle_trip_trip_id=f"TRIP_{i+2}",
                vehicle_trip_route_id="ROUTE_001",
                vehicle_vehicle_id=f"VEH_{i+2}",
                vehicle_position_latitude=9.9 + i * 0.01,
                vehicle_position_longitude=-84.0 + i * 0.01,
                vehicle_timestamp=timezone.now(),
            )

        result = serialize_route_vehicles("ROUTE_001")

        assert result["count"] == len(result["vehicles"])
        assert result["count"] == 4  # 1 from fixture + 3 created

    def test_serialize_route_vehicles_timestamp_present(self, vehicle_position):
        """Test that snapshot includes generation timestamp."""
        result = serialize_route_vehicles("ROUTE_001")

        assert "timestamp" in result
        # Should be valid ISO 8601 timestamp
        datetime.fromisoformat(result["timestamp"].replace("Z", "+00:00"))


# Integration tests
@pytest.mark.django_db
class TestSerializersIntegration:
    """Integration tests combining multiple serializers."""

    def test_full_trip_update_with_all_components(
        self, trip_update, vehicle_position, stop_time_update
    ):
        """Test complete trip update with vehicle and stops."""
        result = serialize_trip_update(trip_update, include_stops=True)

        # Verify all components are present
        assert result["trip"]["trip_id"] == "CR-SJ-01-123"
        assert "position" in result["vehicle"]
        assert len(result["stop_time_updates"]) > 0

        # Verify data consistency
        assert result["vehicle"]["id"] == vehicle_position.vehicle_vehicle_id
        assert result["stop_time_updates"][0]["stop_id"] == "STOP_123"

    def test_route_vehicles_contains_properly_serialized_vehicles(
        self, vehicle_position
    ):
        """Test that route snapshot contains fully serialized vehicles."""
        result = serialize_route_vehicles("ROUTE_001")

        assert result["count"] > 0
        vehicle = result["vehicles"][0]

        # Verify vehicle has all expected keys
        assert "trip" in vehicle
        assert "vehicle" in vehicle
        assert "position" in vehicle
        assert "timestamp" in vehicle
