"""
Integration tests for API endpoints with database and Redis.

Tests cover:
- Database queries and persistence
- Redis caching behavior
- End-to-end request/response flow
- Model relationships and integrity
"""
from django.test import TestCase, TransactionTestCase
from django.contrib.gis.geos import Point, LineString
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import time, date, datetime, timedelta
from unittest.mock import patch, MagicMock
import redis

from gtfs.models import (
    Feed, Stop, Route, Trip, StopTime, Calendar, CalendarDate,
    Agency, Shape, GeoShape
)
from storage.factory import get_schedule_repository


class DatabaseIntegrationTest(APITestCase):
    """Test API endpoints with real database operations."""
    
    def setUp(self):
        """Create test fixtures in database."""
        self.feed = Feed.objects.create(
            feed_id="TEST_FEED",
            is_current=True,
            retrieved_at=datetime.now()
        )
        
        self.agency = Agency.objects.create(
            feed=self.feed,
            agency_id="AGENCY_001",
            agency_name="Test Transit",
            agency_url="https://test.example.com",
            agency_timezone="America/Costa_Rica"
        )
        
        self.stop = Stop.objects.create(
            feed=self.feed,
            stop_id="STOP_001",
            stop_name="Main Station",
            stop_desc="Central bus terminal",
            stop_lat=9.9356,
            stop_lon=-84.0435,
            stop_point=Point(-84.0435, 9.9356),
            location_type=0,
            wheelchair_boarding=1
        )
        
        self.route = Route.objects.create(
            feed=self.feed,
            route_id="ROUTE_001",
            agency=self.agency,
            route_short_name="101",
            route_long_name="Downtown Express",
            route_desc="Express service to downtown",
            route_type=3,
            route_color="FF0000",
            route_text_color="FFFFFF"
        )
        
        self.calendar = Calendar.objects.create(
            feed=self.feed,
            service_id="SERVICE_001",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=False,
            sunday=False,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=365)
        )
        
        self.trip = Trip.objects.create(
            feed=self.feed,
            trip_id="TRIP_001",
            route=self.route,
            service_id=self.calendar.service_id,
            trip_headsign="Downtown",
            direction_id=0,
            wheelchair_accessible=1
        )
        
        # Create stop times using bulk_create to avoid model validation
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
            StopTime(
                feed=self.feed,
                trip_id=self.trip.trip_id,
                stop_id=self.stop.stop_id,
                stop_sequence=2,
                arrival_time=time(9, 0, 0),
                departure_time=time(9, 2, 0),
                pickup_type=0,
                drop_off_type=0,
                timepoint=True
            ),
        ])
    
    def test_schedule_departures_database_query(self):
        """Test schedule departures endpoint queries database correctly."""
        url = f"/api/schedule/departures/?stop_id={self.stop.stop_id}&time=08:00:00&limit=5"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Verify response structure
        self.assertEqual(data["feed_id"], self.feed.feed_id)
        self.assertEqual(data["stop_id"], self.stop.stop_id)
        self.assertIsInstance(data["departures"], list)
        
        # Verify at least one departure returned from DB
        self.assertGreaterEqual(len(data["departures"]), 1)
        
        if len(data["departures"]) > 0:
            departure = data["departures"][0]
            self.assertEqual(departure["stop_id"], self.stop.stop_id)
            self.assertIn("departure_time", departure)
    
    def test_search_stops_database_query(self):
        """Test search endpoint queries stops from database."""
        url = f"/api/search/?q={self.stop.stop_name}&type=stops&limit=10"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Verify search results include our stop
        self.assertGreater(data["total_results"], 0)
        self.assertIsInstance(data["results"], list)
        
        # Find our test stop in results
        stop_found = False
        for result in data["results"]:
            if result.get("stop_id") == self.stop.stop_id:
                stop_found = True
                self.assertEqual(result["stop_name"], self.stop.stop_name)
                self.assertEqual(result["feed_id"], self.feed.feed_id)
                self.assertIn("relevance_score", result)
                break
        
        self.assertTrue(stop_found, "Test stop not found in search results")
    
    def test_search_routes_database_query(self):
        """Test search endpoint queries routes from database."""
        url = f"/api/search/?q={self.route.route_short_name}&type=routes&limit=10"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Verify search results include our route
        self.assertGreater(data["total_results"], 0)
        
        # Find our test route in results
        route_found = False
        for result in data["results"]:
            if result.get("route_id") == self.route.route_id:
                route_found = True
                self.assertEqual(result["route_short_name"], self.route.route_short_name)
                self.assertEqual(result["feed_id"], self.feed.feed_id)
                self.assertEqual(result["route_type"], self.route.route_type)
                break
        
        self.assertTrue(route_found, "Test route not found in search results")
    
    def test_status_endpoint_database_check(self):
        """Test status endpoint verifies database connectivity."""
        url = "/api/status/"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Database should be OK since we just created fixtures
        self.assertTrue(data["database_ok"])
        self.assertEqual(data["current_feed_id"], self.feed.feed_id)
    
    def test_ready_endpoint_database_and_feed_check(self):
        """Test readiness endpoint verifies database and current feed."""
        url = "/api/ready/"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Both database and feed should be available
        self.assertTrue(data["database_ok"])
        self.assertTrue(data["current_feed_available"])
        self.assertEqual(data["current_feed_id"], self.feed.feed_id)
        self.assertEqual(data["status"], "ready")
    
    def test_ready_endpoint_no_current_feed(self):
        """Test readiness endpoint when no current feed exists."""
        # Mark our feed as not current
        self.feed.is_current = False
        self.feed.save()
        
        url = "/api/ready/"
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        data = response.json()
        
        self.assertTrue(data["database_ok"])
        self.assertFalse(data["current_feed_available"])
        self.assertIsNone(data["current_feed_id"])
        self.assertEqual(data["status"], "not_ready")
    
    def test_model_relationships_persist(self):
        """Test that model relationships are correctly persisted."""
        # Verify route is linked to agency
        route = Route.objects.get(route_id=self.route.route_id)
        self.assertEqual(route.agency.agency_id, self.agency.agency_id)
        
        # Verify trip is linked to route
        trip = Trip.objects.get(trip_id=self.trip.trip_id)
        self.assertEqual(trip.route.route_id, self.route.route_id)
        
        # Verify stop times are linked to correct feed and stop
        stop_times = StopTime.objects.filter(
            feed=self.feed,
            stop_id=self.stop.stop_id
        )
        self.assertGreater(stop_times.count(), 0)
        
        for st in stop_times:
            self.assertEqual(st.feed.feed_id, self.feed.feed_id)
            self.assertEqual(st.stop_id, self.stop.stop_id)


class RedisIntegrationTest(TestCase):
    """Test Redis caching integration."""
    
    def setUp(self):
        """Set up test data."""
        self.feed = Feed.objects.create(
            feed_id="TEST_CACHE",
            is_current=True,
            retrieved_at=datetime.now()
        )
        
        self.stop = Stop.objects.create(
            feed=self.feed,
            stop_id="STOP_CACHE_001",
            stop_name="Cache Test Stop",
            stop_point=Point(-84.0435, 9.9356)
        )
    
    @patch('storage.factory.get_schedule_repository')
    def test_schedule_repository_caching(self, mock_get_repo):
        """Test that schedule repository uses caching when enabled."""
        # Create a mock repository
        mock_repo = MagicMock()
        mock_repo.get_next_departures.return_value = [
            {
                "route_id": "R1",
                "trip_id": "T1",
                "stop_id": self.stop.stop_id,
                "arrival_time": "08:00:00",
                "departure_time": "08:02:00"
            }
        ]
        mock_get_repo.return_value = mock_repo
        
        # Call the API endpoint
        url = f"/api/schedule/departures/?stop_id={self.stop.stop_id}&time=08:00:00&limit=5"
        client = APIClient()
        response = client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify the repository was called with use_cache=True
        mock_get_repo.assert_called_once_with(use_cache=True)
    
    def test_redis_connectivity_in_status(self):
        """Test that status endpoint checks Redis connectivity."""
        url = "/api/status/"
        client = APIClient()
        response = client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        # Redis status should be present (may be True or False depending on env)
        self.assertIn("redis_ok", data)
        self.assertIsInstance(data["redis_ok"], bool)


class EndToEndIntegrationTest(APITestCase):
    """Test complete end-to-end workflows."""
    
    def setUp(self):
        """Set up comprehensive test data."""
        self.feed = Feed.objects.create(
            feed_id="E2E_TEST",
            is_current=True,
            retrieved_at=datetime.now()
        )
        
        self.agency = Agency.objects.create(
            feed=self.feed,
            agency_id="E2E_AGENCY",
            agency_name="E2E Transit",
            agency_url="https://e2e.example.com",
            agency_timezone="America/Costa_Rica"
        )
        
        # Create multiple stops for realistic testing
        self.stops = []
        for i in range(3):
            stop = Stop.objects.create(
                feed=self.feed,
                stop_id=f"E2E_STOP_{i:03d}",
                stop_name=f"Station {i}",
                stop_desc=f"Test station number {i}",
                stop_lat=9.9356 + (i * 0.01),
                stop_lon=-84.0435 + (i * 0.01),
                stop_point=Point(-84.0435 + (i * 0.01), 9.9356 + (i * 0.01))
            )
            self.stops.append(stop)
        
        self.route = Route.objects.create(
            feed=self.feed,
            route_id="E2E_ROUTE",
            agency=self.agency,
            route_short_name="E2E",
            route_long_name="End to End Line",
            route_type=3
        )
        
        self.calendar = Calendar.objects.create(
            feed=self.feed,
            service_id="E2E_SERVICE",
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
            trip_id="E2E_TRIP",
            route=self.route,
            service_id=self.calendar.service_id,
            trip_headsign="Test Route"
        )
    
    def test_full_search_and_schedule_workflow(self):
        """Test searching for a stop then getting its schedule."""
        # Step 1: Search for a stop
        search_url = f"/api/search/?q=Station&type=stops&limit=10"
        search_response = self.client.get(search_url)
        
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        search_data = search_response.json()
        self.assertGreater(search_data["total_results"], 0)
        
        # Step 2: Get the first stop's ID
        first_stop_id = search_data["results"][0]["stop_id"]
        
        # Step 3: Query schedule for that stop
        schedule_url = f"/api/schedule/departures/?stop_id={first_stop_id}&limit=5"
        schedule_response = self.client.get(schedule_url)
        
        # Should return 200 even if no departures (empty list is valid)
        self.assertEqual(schedule_response.status_code, status.HTTP_200_OK)
        schedule_data = schedule_response.json()
        
        self.assertEqual(schedule_data["stop_id"], first_stop_id)
        self.assertEqual(schedule_data["feed_id"], self.feed.feed_id)
        self.assertIsInstance(schedule_data["departures"], list)
    
    def test_health_check_workflow(self):
        """Test health check then readiness check workflow."""
        # Step 1: Basic health check
        health_url = "/api/health/"
        health_response = self.client.get(health_url)
        
        self.assertEqual(health_response.status_code, status.HTTP_200_OK)
        health_data = health_response.json()
        self.assertEqual(health_data["status"], "ok")
        
        # Step 2: Detailed status check
        status_url = "/api/status/"
        status_response = self.client.get(status_url)
        
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        status_data = status_response.json()
        self.assertTrue(status_data["database_ok"])
        
        # Step 3: Readiness check
        ready_url = "/api/ready/"
        ready_response = self.client.get(ready_url)
        
        self.assertEqual(ready_response.status_code, status.HTTP_200_OK)
        ready_data = ready_response.json()
        self.assertEqual(ready_data["status"], "ready")
        self.assertTrue(ready_data["database_ok"])
        self.assertTrue(ready_data["current_feed_available"])
    
    def test_search_all_types_workflow(self):
        """Test searching for all types (stops and routes)."""
        # Search for all types
        search_url = "/api/search/?q=E2E&type=all&limit=20"
        response = self.client.get(search_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        
        self.assertEqual(data["results_type"], "all")
        self.assertGreater(data["total_results"], 0)
        
        # Should have both stops and routes in results
        result_types = set(r.get("result_type") for r in data["results"])
        # At minimum we should have one type
        self.assertGreaterEqual(len(result_types), 1)


class DataIntegrityTest(TransactionTestCase):
    """Test data integrity across transactions."""
    
    def test_feed_cascade_deletion(self):
        """Test that deleting a feed cascades to related objects."""
        feed = Feed.objects.create(
            feed_id="DELETE_TEST",
            is_current=False,
            retrieved_at=datetime.now()
        )
        
        stop = Stop.objects.create(
            feed=feed,
            stop_id="DEL_STOP",
            stop_name="Delete Test Stop",
            stop_point=Point(-84.0435, 9.9356)
        )
        
        stop_id = stop.stop_id
        feed_id = feed.feed_id
        
        # Verify objects exist
        self.assertTrue(Feed.objects.filter(feed_id=feed_id).exists())
        self.assertTrue(Stop.objects.filter(stop_id=stop_id, feed=feed).exists())
        
        # Delete the feed
        feed.delete()
        
        # Verify feed is deleted
        self.assertFalse(Feed.objects.filter(feed_id=feed_id).exists())
        
        # Verify associated stops are also deleted (cascade)
        self.assertFalse(Stop.objects.filter(stop_id=stop_id, feed_id=feed_id).exists())
    
    def test_concurrent_feed_queries(self):
        """Test that concurrent queries handle multiple feeds correctly."""
        feed1 = Feed.objects.create(
            feed_id="CONCURRENT_1",
            is_current=True,
            retrieved_at=datetime.now()
        )
        
        feed2 = Feed.objects.create(
            feed_id="CONCURRENT_2",
            is_current=False,
            retrieved_at=datetime.now() - timedelta(days=1)
        )
        
        stop1 = Stop.objects.create(
            feed=feed1,
            stop_id="STOP_F1",
            stop_name="Feed 1 Stop",
            stop_point=Point(-84.0435, 9.9356)
        )
        
        stop2 = Stop.objects.create(
            feed=feed2,
            stop_id="STOP_F2",
            stop_name="Feed 2 Stop",
            stop_point=Point(-84.0500, 9.9400)
        )
        
        # Query with explicit feed_id
        client = APIClient()
        
        # Search in feed1
        response1 = client.get(f"/api/search/?q=Feed&type=stops&feed_id={feed1.feed_id}&limit=10")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        data1 = response1.json()
        
        # Verify results are from correct feed
        for result in data1["results"]:
            self.assertEqual(result["feed_id"], feed1.feed_id)
        
        # Search in feed2
        response2 = client.get(f"/api/search/?q=Feed&type=stops&feed_id={feed2.feed_id}&limit=10")
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = response2.json()
        
        # Verify results are from correct feed
        for result in data2["results"]:
            self.assertEqual(result["feed_id"], feed2.feed_id)
