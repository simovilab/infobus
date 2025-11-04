"""
Unit tests for API serializers.

Tests cover:
- Field validation (required, optional, types)
- Null handling and defaults
- Nested serializers
- Edge cases and error handling
"""
from django.test import TestCase
from rest_framework.test import APITestCase
from datetime import datetime, date, time, timedelta
from decimal import Decimal

from api.serializers import (
    # Basic serializers
    NextArrivalSerializer,
    NextTripSerializer,
    NextStopSerializer,
    NextStopSequenceSerializer,
    ProgressionSerializer,
    
    # Route/Stop serializers
    RouteStopSerializer,
    RouteStopFeatureSerializer,
    RouteStopPropertiesSerializer,
    RouteStopGeometrySerializer,
    RoutesAtStopSerializer,
    
    # Schedule serializers
    DalDepartureSerializer,
    DalDeparturesResponseSerializer,
    
    # Search serializers
    SearchStopResultSerializer,
    SearchRouteResultSerializer,
    SearchResultsSerializer,
    
    # Health check serializers
    HealthCheckSerializer,
    ReadinessCheckSerializer,
)


class ProgressionSerializerTest(TestCase):
    """Test ProgressionSerializer field validation."""
    
    def test_valid_data(self):
        data = {
            "position_in_shape": 0.42,
            "current_stop_sequence": 5,
            "current_status": "IN_TRANSIT_TO",
            "occupancy_status": "FEW_SEATS_AVAILABLE"
        }
        serializer = ProgressionSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["position_in_shape"], 0.42)
        self.assertEqual(serializer.validated_data["current_stop_sequence"], 5)
    
    def test_missing_required_fields(self):
        data = {"position_in_shape": 0.42}
        serializer = ProgressionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("current_stop_sequence", serializer.errors)
        self.assertIn("current_status", serializer.errors)
    
    def test_invalid_types(self):
        data = {
            "position_in_shape": "not_a_float",
            "current_stop_sequence": "not_an_int",
            "current_status": "IN_TRANSIT_TO",
            "occupancy_status": "FEW_SEATS_AVAILABLE"
        }
        serializer = ProgressionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("position_in_shape", serializer.errors)
        self.assertIn("current_stop_sequence", serializer.errors)


class NextArrivalSerializerTest(TestCase):
    """Test NextArrivalSerializer with nested progression."""
    
    def test_valid_data_with_progression(self):
        data = {
            "trip_id": "trip_001",
            "route_id": "route_001",
            "route_short_name": "101",
            "route_long_name": "Downtown Express",
            "trip_headsign": "City Center",
            "wheelchair_accessible": "1",
            "arrival_time": "2025-10-30T14:30:00Z",
            "departure_time": "2025-10-30T14:32:00Z",
            "in_progress": True,
            "progression": {
                "position_in_shape": 0.65,
                "current_stop_sequence": 8,
                "current_status": "STOPPED_AT",
                "occupancy_status": "STANDING_ROOM_ONLY"
            }
        }
        serializer = NextArrivalSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["trip_id"], "trip_001")
        self.assertTrue(serializer.validated_data["in_progress"])
        self.assertIsNotNone(serializer.validated_data["progression"])
    
    def test_valid_data_without_progression(self):
        """Test that progression field is required, use dummy data when not in progress."""
        data = {
            "trip_id": "trip_002",
            "route_id": "route_002",
            "route_short_name": "102",
            "route_long_name": "University Line",
            "trip_headsign": "Campus",
            "wheelchair_accessible": "0",
            "arrival_time": "2025-10-30T15:00:00Z",
            "departure_time": "2025-10-30T15:02:00Z",
            "in_progress": False,
            "progression": {
                "position_in_shape": 0.0,
                "current_stop_sequence": 0,
                "current_status": "SCHEDULED",
                "occupancy_status": "EMPTY"
            }
        }
        serializer = NextArrivalSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertFalse(serializer.validated_data["in_progress"])
    
    def test_missing_required_fields(self):
        data = {
            "trip_id": "trip_001",
            "route_id": "route_001"
        }
        serializer = NextArrivalSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        # Check some of the required fields are reported as missing
        self.assertIn("route_short_name", serializer.errors)
        self.assertIn("arrival_time", serializer.errors)


class NextTripSerializerTest(TestCase):
    """Test NextTripSerializer with many arrivals."""
    
    def test_valid_data_with_multiple_arrivals(self):
        data = {
            "stop_id": "stop_001",
            "timestamp": "2025-10-30T14:00:00Z",
            "next_arrivals": [
                {
                    "trip_id": "trip_001",
                    "route_id": "route_001",
                    "route_short_name": "101",
                    "route_long_name": "Downtown",
                    "trip_headsign": "City",
                    "wheelchair_accessible": "1",
                    "arrival_time": "2025-10-30T14:30:00Z",
                    "departure_time": "2025-10-30T14:32:00Z",
                    "in_progress": True,
                    "progression": {
                        "position_in_shape": 0.5,
                        "current_stop_sequence": 5,
                        "current_status": "IN_TRANSIT_TO",
                        "occupancy_status": "MANY_SEATS_AVAILABLE"
                    }
                },
                {
                    "trip_id": "trip_002",
                    "route_id": "route_002",
                    "route_short_name": "102",
                    "route_long_name": "University",
                    "trip_headsign": "Campus",
                    "wheelchair_accessible": "0",
                    "arrival_time": "2025-10-30T15:00:00Z",
                    "departure_time": "2025-10-30T15:02:00Z",
                    "in_progress": False,
                    "progression": {
                        "position_in_shape": 0.0,
                        "current_stop_sequence": 0,
                        "current_status": "SCHEDULED",
                        "occupancy_status": "EMPTY"
                    }
                }
            ]
        }
        serializer = NextTripSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(serializer.validated_data["next_arrivals"]), 2)
        self.assertEqual(serializer.validated_data["stop_id"], "stop_001")
    
    def test_empty_arrivals_list(self):
        data = {
            "stop_id": "stop_001",
            "timestamp": "2025-10-30T14:00:00Z",
            "next_arrivals": []
        }
        serializer = NextTripSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(serializer.validated_data["next_arrivals"]), 0)


class NextStopSequenceSerializerTest(TestCase):
    """Test NextStopSequenceSerializer."""
    
    def test_valid_data(self):
        data = {
            "stop_sequence": 1,
            "stop_id": "stop_001",
            "stop_name": "Main Station",
            "stop_lat": 9.9356,
            "stop_lon": -84.0435,
            "arrival": "2025-10-30T14:30:00Z",
            "departure": "2025-10-30T14:32:00Z"
        }
        serializer = NextStopSequenceSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["stop_sequence"], 1)
        self.assertEqual(serializer.validated_data["stop_name"], "Main Station")


class NextStopSerializerTest(TestCase):
    """Test NextStopSerializer with stop sequences."""
    
    def test_valid_data_with_sequences(self):
        data = {
            "trip_id": "trip_001",
            "start_date": "2025-10-30",
            "start_time": "14:00:00",
            "next_stop_sequence": [
                {
                    "stop_sequence": 1,
                    "stop_id": "stop_001",
                    "stop_name": "First Stop",
                    "stop_lat": 9.9356,
                    "stop_lon": -84.0435,
                    "arrival": "2025-10-30T14:30:00Z",
                    "departure": "2025-10-30T14:32:00Z"
                },
                {
                    "stop_sequence": 2,
                    "stop_id": "stop_002",
                    "stop_name": "Second Stop",
                    "stop_lat": 9.9400,
                    "stop_lon": -84.0500,
                    "arrival": "2025-10-30T14:40:00Z",
                    "departure": "2025-10-30T14:42:00Z"
                }
            ]
        }
        serializer = NextStopSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(len(serializer.validated_data["next_stop_sequence"]), 2)


class RouteStopSerializerTest(TestCase):
    """Test GeoJSON route stop serializers."""
    
    def test_valid_geojson_structure(self):
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [-84.0435, 9.9356]
                    },
                    "properties": {
                        "route_id": "route_001",
                        "shape_id": "shape_001",
                        "stop_id": "stop_001",
                        "stop_name": "Main Station",
                        "stop_desc": "Central bus terminal",
                        "stop_sequence": 1,
                        "timepoint": True,
                        "wheelchair_boarding": 1
                    }
                }
            ]
        }
        serializer = RouteStopSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["type"], "FeatureCollection")
        self.assertEqual(len(serializer.validated_data["features"]), 1)


class DalDepartureSerializerTest(TestCase):
    """Test DAL departure serializer."""
    
    def test_valid_departure(self):
        data = {
            "route_id": "route_001",
            "route_short_name": "101",
            "route_long_name": "Downtown Express",
            "trip_id": "trip_001",
            "stop_id": "stop_001",
            "headsign": "City Center",
            "direction_id": 0,
            "arrival_time": "14:30:00",
            "departure_time": "14:32:00"
        }
        serializer = DalDepartureSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["route_id"], "route_001")
    
    def test_nullable_fields(self):
        data = {
            "route_id": "route_001",
            "route_short_name": None,
            "route_long_name": None,
            "trip_id": "trip_001",
            "stop_id": "stop_001",
            "headsign": None,
            "direction_id": None,
            "arrival_time": None,
            "departure_time": None
        }
        serializer = DalDepartureSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class DalDeparturesResponseSerializerTest(TestCase):
    """Test DAL departures response serializer."""
    
    def test_valid_response(self):
        data = {
            "feed_id": "TEST",
            "stop_id": "stop_001",
            "service_date": "2025-10-30",
            "from_time": "14:00:00",
            "limit": 10,
            "departures": [
                {
                    "route_id": "route_001",
                    "route_short_name": "101",
                    "route_long_name": "Downtown",
                    "trip_id": "trip_001",
                    "stop_id": "stop_001",
                    "headsign": "City",
                    "direction_id": 0,
                    "arrival_time": "14:30:00",
                    "departure_time": "14:32:00"
                }
            ]
        }
        serializer = DalDeparturesResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["feed_id"], "TEST")
        self.assertEqual(len(serializer.validated_data["departures"]), 1)


class SearchStopResultSerializerTest(TestCase):
    """Test search stop result serializer."""
    
    def test_valid_stop_result(self):
        data = {
            "stop_id": "stop_001",
            "stop_name": "Main Station",
            "stop_desc": "Central terminal",
            "stop_lat": Decimal("9.9356"),
            "stop_lon": Decimal("-84.0435"),
            "location_type": 0,
            "wheelchair_boarding": 1,
            "feed_id": "TEST",
            "relevance_score": 0.95
        }
        serializer = SearchStopResultSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["stop_id"], "stop_001")
        self.assertEqual(float(serializer.validated_data["relevance_score"]), 0.95)
    
    def test_nullable_optional_fields(self):
        data = {
            "stop_id": "stop_001",
            "stop_name": "Main Station",
            "stop_desc": None,
            "stop_lat": None,
            "stop_lon": None,
            "location_type": None,
            "wheelchair_boarding": None,
            "feed_id": "TEST",
            "relevance_score": 0.5
        }
        serializer = SearchStopResultSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)


class SearchRouteResultSerializerTest(TestCase):
    """Test search route result serializer."""
    
    def test_valid_route_result(self):
        data = {
            "route_id": "route_001",
            "route_short_name": "101",
            "route_long_name": "Downtown Express",
            "route_desc": "Express service to downtown",
            "route_type": 3,
            "route_color": "FF0000",
            "route_text_color": "FFFFFF",
            "agency_name": "City Transit",
            "feed_id": "TEST",
            "relevance_score": 0.89
        }
        serializer = SearchRouteResultSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["route_id"], "route_001")
        self.assertEqual(serializer.validated_data["route_type"], 3)


class SearchResultsSerializerTest(TestCase):
    """Test search results wrapper serializer."""
    
    def test_valid_search_results(self):
        data = {
            "query": "university",
            "results_type": "all",
            "total_results": 5,
            "results": [
                {
                    "stop_id": "stop_001",
                    "stop_name": "University Station",
                    "feed_id": "TEST",
                    "relevance_score": 0.95,
                    "result_type": "stop"
                },
                {
                    "route_id": "route_001",
                    "route_short_name": "U1",
                    "feed_id": "TEST",
                    "relevance_score": 0.85,
                    "result_type": "route"
                }
            ]
        }
        serializer = SearchResultsSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["query"], "university")
        self.assertEqual(serializer.validated_data["total_results"], 5)


class HealthCheckSerializerTest(TestCase):
    """Test health check serializer."""
    
    def test_valid_health_check(self):
        data = {
            "status": "ok",
            "timestamp": datetime.now()
        }
        serializer = HealthCheckSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["status"], "ok")
    
    def test_degraded_status(self):
        data = {
            "status": "degraded",
            "timestamp": datetime.now()
        }
        serializer = HealthCheckSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["status"], "degraded")


class ReadinessCheckSerializerTest(TestCase):
    """Test readiness check serializer."""
    
    def test_valid_ready_state(self):
        data = {
            "status": "ready",
            "database_ok": True,
            "current_feed_available": True,
            "current_feed_id": "TEST",
            "timestamp": datetime.now()
        }
        serializer = ReadinessCheckSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["status"], "ready")
        self.assertTrue(serializer.validated_data["database_ok"])
    
    def test_not_ready_state(self):
        data = {
            "status": "not_ready",
            "database_ok": True,
            "current_feed_available": False,
            "current_feed_id": None,
            "timestamp": datetime.now()
        }
        serializer = ReadinessCheckSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["status"], "not_ready")
        self.assertFalse(serializer.validated_data["current_feed_available"])
        self.assertIsNone(serializer.validated_data["current_feed_id"])
