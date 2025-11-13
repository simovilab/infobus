"""
Tests for GraphQL functionality in Infobús project.
"""
import json
from django.test import TestCase, Client
from django.urls import reverse
from gtfs.models import (
    GTFSProvider, Feed, Agency, Stop, Route, Trip, StopTime, Calendar
)


class GraphQLTestCase(TestCase):
    """Test GraphQL queries and schema configuration"""
    
    def setUp(self):
        self.client = Client()
        self.graphql_url = "/graphql/"
        
        # Create test data
        self.gtfs_provider = GTFSProvider.objects.create(
            code="TEST",
            name="Test Provider",
            timezone="America/Costa_Rica",
            is_active=True
        )
        
        self.feed = Feed.objects.create(
            feed_id="test_feed",
            gtfs_provider=self.gtfs_provider
        )
        
        self.agency = Agency.objects.create(
            feed=self.feed,
            agency_id="test_agency",
            agency_name="Test Agency",
            agency_url="http://test.com",
            agency_timezone="America/Costa_Rica"
        )
        
        self.stop = Stop.objects.create(
            feed=self.feed,
            stop_id="test_stop",
            stop_name="Test Stop",
            stop_lat=9.9281,
            stop_lon=-84.0907
        )
        
        # Create additional test data for new models
        self.route = Route.objects.create(
            feed=self.feed,
            route_id="test_route",
            agency_id="test_agency",
            route_short_name="R001",
            route_long_name="Test Route 001",
            route_type=3  # Bus
        )
        
        self.calendar = Calendar.objects.create(
            feed=self.feed,
            service_id="test_service",
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=False,
            sunday=False,
            start_date="2024-01-01",
            end_date="2024-12-31"
        )
        
        self.trip = Trip.objects.create(
            feed=self.feed,
            route_id="test_route",
            service_id="test_service",
            trip_id="test_trip",
            trip_headsign="Downtown",
            direction_id=0,
            wheelchair_accessible=1,
            bikes_allowed=1
        )
        
        self.stop_time = StopTime.objects.create(
            feed=self.feed,
            trip_id="test_trip",
            stop_id="test_stop",
            arrival_time="08:30:00",
            departure_time="08:30:00",
            stop_sequence=1,
            pickup_type=0,
            drop_off_type=0
        )
    
    def _graphql_query(self, query, variables=None):
        """Helper method to execute GraphQL queries"""
        body = {"query": query}
        if variables:
            body["variables"] = variables
        
        response = self.client.post(
            self.graphql_url,
            json.dumps(body),
            content_type="application/json"
        )
        return response
    
    def test_hello_query(self):
        """Test the basic hello query"""
        query = """
        query {
            hello {
                message
            }
        }
        """
        
        response = self._graphql_query(query)
        self.assertEqual(response.status_code, 200)
        
        content = json.loads(response.content)
        self.assertNotIn("errors", content)
        self.assertEqual(
            content["data"]["hello"]["message"],
            "¡Hola desde GraphQL de Infobús!"
        )
    
    def test_agencies_query(self):
        """Test querying agencies"""
        query = """
        query {
            agencies {
                id
                agencyId
                agencyName
                agencyUrl
                agencyTimezone
            }
        }
        """
        
        response = self._graphql_query(query)
        self.assertEqual(response.status_code, 200)
        
        content = json.loads(response.content)
        self.assertNotIn("errors", content)
        agencies = content["data"]["agencies"]
        self.assertEqual(len(agencies), 1)
        self.assertEqual(agencies[0]["agencyName"], "Test Agency")
    
    def test_agency_query(self):
        """Test querying a specific agency"""
        query = """
        query($id: Int!) {
            agency(id: $id) {
                id
                agencyId
                agencyName
            }
        }
        """
        
        response = self._graphql_query(query, {"id": self.agency.id})
        self.assertEqual(response.status_code, 200)
        
        content = json.loads(response.content)
        self.assertNotIn("errors", content)
        agency = content["data"]["agency"]
        self.assertEqual(agency["agencyName"], "Test Agency")
    
    def test_stops_query(self):
        """Test querying stops"""
        query = """
        query {
            stops {
                id
                stopId
                stopName
                stopLat
                stopLon
            }
        }
        """
        
        response = self._graphql_query(query)
        self.assertEqual(response.status_code, 200)
        
        content = json.loads(response.content)
        self.assertNotIn("errors", content)
        stops = content["data"]["stops"]
        self.assertEqual(len(stops), 1)
        self.assertEqual(stops[0]["stopName"], "Test Stop")
    
    def test_gtfs_providers_query(self):
        """Test querying GTFS providers"""
        query = """
        query {
            gtfsProviders {
                providerId
                code
                name
                timezone
                isActive
            }
        }
        """
        
        response = self._graphql_query(query)
        self.assertEqual(response.status_code, 200)
        
        content = json.loads(response.content)
        self.assertNotIn("errors", content)
        providers = content["data"]["gtfsProviders"]
        self.assertEqual(len(providers), 1)
        self.assertEqual(providers[0]["name"], "Test Provider")
    
    def test_graphql_endpoint_exists(self):
        """Test that GraphQL endpoint is accessible"""
        response = self.client.get(self.graphql_url)
        # Should return 400 for GET without query, but endpoint should exist
        self.assertIn(response.status_code, [200, 400, 405])