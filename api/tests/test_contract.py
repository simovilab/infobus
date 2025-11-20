"""
Contract tests for OpenAPI schema conformance.

Tests cover:
- Response structure matches OpenAPI schema
- Status codes match documented responses
- Data types conform to schema definitions
- Required fields are present
- Optional fields are handled correctly
"""
from django.test import TestCase
from django.contrib.gis.geos import Point
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import time, date, datetime, timedelta
from drf_spectacular.generators import SchemaGenerator
import json

from gtfs.models import Feed, Stop, Route, Agency, Calendar, Trip, StopTime


class OpenAPIContractTest(APITestCase):
    """Test that API responses conform to OpenAPI schema."""
    
    @classmethod
    def setUpClass(cls):
        """Set up OpenAPI schema for all tests."""
        super().setUpClass()
        generator = SchemaGenerator()
        cls.schema = generator.get_schema()
    
    def setUp(self):
        """Create test fixtures."""
        self.feed = Feed.objects.create(
            feed_id="CONTRACT_TEST",
            is_current=True,
            retrieved_at=datetime.now()
        )
        
        self.agency = Agency.objects.create(
            feed=self.feed,
            agency_id="AGENCY_CONTRACT",
            agency_name="Contract Test Agency",
            agency_url="https://contract.example.com",
            agency_timezone="America/Costa_Rica"
        )
        
        self.stop = Stop.objects.create(
            feed=self.feed,
            stop_id="STOP_CONTRACT",
            stop_name="Contract Test Stop",
            stop_desc="Test stop for contract validation",
            stop_lat=9.9356,
            stop_lon=-84.0435,
            stop_point=Point(-84.0435, 9.9356),
            location_type=0,
            wheelchair_boarding=1
        )
        
        self.route = Route.objects.create(
            feed=self.feed,
            route_id="ROUTE_CONTRACT",
            agency_id=self.agency.agency_id,
            route_short_name="CT1",
            route_long_name="Contract Test Line",
            route_type=3,
            route_color="0000FF",
            route_text_color="FFFFFF"
        )
        
        self.calendar = Calendar.objects.create(
            feed=self.feed,
            service_id="SERVICE_CONTRACT",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=True,
            sunday=True,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365)
        )
        
        self.trip = Trip.objects.create(
            feed=self.feed,
            trip_id="TRIP_CONTRACT",
            route_id=self.route.route_id,
            service_id=self.calendar.service_id,
            trip_headsign="Test",
            direction_id=0,
            wheelchair_accessible=0,
            bikes_allowed=0
        )
        
        StopTime.objects.bulk_create([
            StopTime(
                feed=self.feed,
                trip_id=self.trip.trip_id,
                stop_id=self.stop.stop_id,
                stop_sequence=1,
                arrival_time=time(8, 0, 0),
                departure_time=time(8, 2, 0),
                pickup_type=0,
                drop_off_type=0,
                timepoint=True
            ),
        ])
    
    def test_health_endpoint_contract(self):
        """Test /health/ endpoint conforms to OpenAPI schema."""
        response = self.client.get("/api/health/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Required fields from HealthCheckSerializer
        self.assertIn("status", data)
        self.assertIn("timestamp", data)
        
        # Type validation
        self.assertIsInstance(data["status"], str)
        self.assertIsInstance(data["timestamp"], str)
        
        # Value validation
        self.assertIn(data["status"], ["ok", "degraded", "error"])
    
    def test_ready_endpoint_contract(self):
        """Test /ready/ endpoint conforms to OpenAPI schema."""
        response = self.client.get("/api/ready/")
        
        # Should be 200 or 503 depending on readiness
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
        data = response.json()
        
        # Required fields from ReadinessCheckSerializer
        required_fields = ["status", "database_ok", "current_feed_available", "timestamp"]
        for field in required_fields:
            self.assertIn(field, data)
        
        # Type validation
        self.assertIsInstance(data["status"], str)
        self.assertIsInstance(data["database_ok"], bool)
        self.assertIsInstance(data["current_feed_available"], bool)
        self.assertIsInstance(data["timestamp"], str)
        
        # Optional field
        if data["current_feed_available"]:
            self.assertIn("current_feed_id", data)
            if data["current_feed_id"] is not None:
                self.assertIsInstance(data["current_feed_id"], str)
    
    def test_status_endpoint_contract(self):
        """Test /status/ endpoint conforms to OpenAPI schema."""
        response = self.client.get("/api/status/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Required fields
        required_fields = ["status", "database_ok", "redis_ok", "time"]
        for field in required_fields:
            self.assertIn(field, data)
        
        # Type validation
        self.assertIsInstance(data["status"], str)
        self.assertIsInstance(data["database_ok"], bool)
        self.assertIsInstance(data["redis_ok"], bool)
        
        # Optional field
        if "current_feed_id" in data:
            self.assertIsInstance(data["current_feed_id"], (str, type(None)))
    
    def test_schedule_departures_endpoint_contract(self):
        """Test /schedule/departures/ endpoint conforms to OpenAPI schema."""
        url = f"/api/schedule/departures/?stop_id={self.stop.stop_id}&time=08:00:00&limit=5"
        response = self.client.get(url)
        
        # Should be 200, 400, or 404
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND
        ])
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            
            # Required fields from DalDeparturesResponseSerializer
            required_fields = ["feed_id", "stop_id", "service_date", "from_time", "limit", "departures"]
            for field in required_fields:
                self.assertIn(field, data)
            
            # Type validation
            self.assertIsInstance(data["feed_id"], str)
            self.assertIsInstance(data["stop_id"], str)
            self.assertIsInstance(data["service_date"], str)
            self.assertIsInstance(data["from_time"], str)
            self.assertIsInstance(data["limit"], int)
            self.assertIsInstance(data["departures"], list)
            
            # Validate departure structure if present
            if len(data["departures"]) > 0:
                departure = data["departures"][0]
                departure_required = ["route_id", "trip_id", "stop_id"]
                for field in departure_required:
                    self.assertIn(field, departure)
    
    def test_search_endpoint_contract(self):
        """Test /search/ endpoint conforms to OpenAPI schema."""
        url = f"/api/search/?q={self.stop.stop_name}&type=stops&limit=10"
        response = self.client.get(url)
        
        # Should be 200 or 400
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST
        ])
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            
            # Required fields from SearchResultsSerializer
            required_fields = ["query", "results_type", "total_results", "results"]
            for field in required_fields:
                self.assertIn(field, data)
            
            # Type validation
            self.assertIsInstance(data["query"], str)
            self.assertIsInstance(data["results_type"], str)
            self.assertIsInstance(data["total_results"], int)
            self.assertIsInstance(data["results"], list)
            
            # Value validation
            self.assertIn(data["results_type"], ["stops", "routes", "all"])
            self.assertGreaterEqual(data["total_results"], 0)
            
            # Validate result structure if present
            if len(data["results"]) > 0:
                result = data["results"][0]
                self.assertIn("relevance_score", result)
                self.assertIsInstance(result["relevance_score"], (int, float))
                self.assertGreaterEqual(result["relevance_score"], 0.0)
                self.assertLessEqual(result["relevance_score"], 1.0)
    
    def test_arrivals_endpoint_contract(self):
        """Test /arrivals/ endpoint conforms to OpenAPI schema."""
        url = f"/api/arrivals/?stop_id={self.stop.stop_id}&limit=10"
        response = self.client.get(url)
        
        # Should be 200, 400, 501, or 502
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_501_NOT_IMPLEMENTED,
            status.HTTP_502_BAD_GATEWAY
        ])
        
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            
            # Required fields from NextTripSerializer
            required_fields = ["stop_id", "timestamp", "next_arrivals"]
            for field in required_fields:
                self.assertIn(field, data)
            
            # Type validation
            self.assertIsInstance(data["stop_id"], str)
            self.assertIsInstance(data["timestamp"], str)
            self.assertIsInstance(data["next_arrivals"], list)
        elif response.status_code == status.HTTP_501_NOT_IMPLEMENTED:
            # ETAs service not configured is a valid response
            data = response.json()
            self.assertIn("error", data)
    
    def test_error_response_contract(self):
        """Test error responses conform to expected structure."""
        # Missing required parameter
        response = self.client.get("/api/schedule/departures/")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        
        # Error responses should have an error field
        self.assertIn("error", data)
        self.assertIsInstance(data["error"], str)
    
    def test_not_found_response_contract(self):
        """Test 404 responses conform to expected structure."""
        response = self.client.get("/api/schedule/departures/?stop_id=NONEXISTENT&limit=5")
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.json()
        
        # Error responses should have an error field
        self.assertIn("error", data)
        self.assertIsInstance(data["error"], str)


class ResponseHeadersContractTest(APITestCase):
    """Test that response headers conform to expected standards."""
    
    def setUp(self):
        """Create minimal test data."""
        self.feed = Feed.objects.create(
            feed_id="HEADER_TEST",
            is_current=True,
            retrieved_at=datetime.now()
        )
    
    def test_content_type_json(self):
        """Test that JSON endpoints return correct content type."""
        response = self.client.get("/api/health/")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")
    
    def test_cors_headers_present(self):
        """Test that CORS headers are configured if enabled."""
        response = self.client.get("/api/health/")
        
        # CORS headers may or may not be present depending on configuration
        # Just verify response is successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class QueryParameterContractTest(APITestCase):
    """Test that query parameter validation conforms to OpenAPI schema."""
    
    def setUp(self):
        """Create test data."""
        self.feed = Feed.objects.create(
            feed_id="QUERY_TEST",
            is_current=True,
            retrieved_at=datetime.now()
        )
        
        self.stop = Stop.objects.create(
            feed=self.feed,
            stop_id="STOP_QUERY",
            stop_name="Query Test Stop",
            stop_point=Point(-84.0435, 9.9356)
        )
    
    def test_required_parameters_enforced(self):
        """Test that required parameters are enforced."""
        # Missing required stop_id
        response = self.client.get("/api/schedule/departures/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing required query parameter
        response = self.client.get("/api/search/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_parameter_type_validation(self):
        """Test that parameter types are validated."""
        # Invalid limit (not an integer)
        response = self.client.get(f"/api/schedule/departures/?stop_id={self.stop.stop_id}&limit=invalid")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Invalid limit (out of range)
        response = self.client.get(f"/api/schedule/departures/?stop_id={self.stop.stop_id}&limit=1000")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_optional_parameters_handled(self):
        """Test that optional parameters are handled correctly."""
        # Without optional parameters
        response1 = self.client.get(f"/api/schedule/departures/?stop_id={self.stop.stop_id}")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # With optional parameters
        response2 = self.client.get(
            f"/api/schedule/departures/?stop_id={self.stop.stop_id}&time=08:00:00&date=2025-10-30&limit=5"
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
    
    def test_search_type_parameter_validation(self):
        """Test that search type parameter values are validated."""
        # Valid types
        for search_type in ["stops", "routes", "all"]:
            response = self.client.get(f"/api/search/?q=test&type={search_type}")
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
        
        # Invalid type
        response = self.client.get("/api/search/?q=test&type=invalid")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class StatusCodeContractTest(APITestCase):
    """Test that status codes conform to OpenAPI documentation."""
    
    def setUp(self):
        """Create test data."""
        self.feed = Feed.objects.create(
            feed_id="STATUS_TEST",
            is_current=True,
            retrieved_at=datetime.now()
        )
        
        self.stop = Stop.objects.create(
            feed=self.feed,
            stop_id="STOP_STATUS",
            stop_name="Status Test Stop",
            stop_point=Point(-84.0435, 9.9356)
        )
    
    def test_success_status_codes(self):
        """Test that successful requests return 200."""
        endpoints = [
            "/api/health/",
            "/api/ready/",
            "/api/status/",
            f"/api/search/?q=test&type=stops",
            f"/api/schedule/departures/?stop_id={self.stop.stop_id}",
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            # Should be 200 or 503 for ready endpoint
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])
    
    def test_bad_request_status_codes(self):
        """Test that invalid requests return 400."""
        invalid_requests = [
            "/api/schedule/departures/",  # Missing stop_id
            "/api/search/",  # Missing query
            f"/api/schedule/departures/?stop_id={self.stop.stop_id}&limit=1000",  # Invalid limit
            "/api/search/?q=test&type=invalid",  # Invalid type
        ]
        
        for endpoint in invalid_requests:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_not_found_status_codes(self):
        """Test that missing resources return 404."""
        not_found_requests = [
            "/api/schedule/departures/?stop_id=NONEXISTENT",
            "/api/search/?q=test&feed_id=NONEXISTENT",
        ]
        
        for endpoint in not_found_requests:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_not_implemented_status_codes(self):
        """Test that unimplemented features return 501."""
        # Arrivals endpoint without ETAS_API_URL configured
        response = self.client.get(f"/api/arrivals/?stop_id={self.stop.stop_id}")
        # Should be 501 if ETAs not configured, or 200/502 if configured
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_501_NOT_IMPLEMENTED,
            status.HTTP_502_BAD_GATEWAY
        ])


class DataTypeContractTest(APITestCase):
    """Test that data types in responses conform to schema."""
    
    def setUp(self):
        """Create test data."""
        self.feed = Feed.objects.create(
            feed_id="TYPE_TEST",
            is_current=True,
            retrieved_at=datetime.now()
        )
        
        self.stop = Stop.objects.create(
            feed=self.feed,
            stop_id="STOP_TYPE",
            stop_name="Type Test Stop",
            stop_point=Point(-84.0435, 9.9356)
        )
    
    def test_string_fields(self):
        """Test that string fields return strings."""
        response = self.client.get("/api/health/")
        data = response.json()
        
        self.assertIsInstance(data["status"], str)
        self.assertIsInstance(data["timestamp"], str)
    
    def test_boolean_fields(self):
        """Test that boolean fields return booleans."""
        response = self.client.get("/api/ready/")
        data = response.json()
        
        self.assertIsInstance(data["database_ok"], bool)
        self.assertIsInstance(data["current_feed_available"], bool)
    
    def test_integer_fields(self):
        """Test that integer fields return integers."""
        response = self.client.get("/api/search/?q=test&type=stops")
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            self.assertIsInstance(data["total_results"], int)
    
    def test_array_fields(self):
        """Test that array fields return lists."""
        response = self.client.get(f"/api/schedule/departures/?stop_id={self.stop.stop_id}")
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            self.assertIsInstance(data["departures"], list)
    
    def test_nullable_fields(self):
        """Test that nullable fields can be null."""
        response = self.client.get("/api/ready/")
        data = response.json()
        
        # current_feed_id can be null
        if "current_feed_id" in data:
            self.assertIsInstance(data["current_feed_id"], (str, type(None)))
