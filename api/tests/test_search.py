from __future__ import annotations

from rest_framework import status
from rest_framework.test import APITestCase
from django.test import TestCase
from gtfs.models import Feed, Stop, Route, Agency


class SearchEndpointTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        """Set up test data for search tests."""
        # Create test feed
        cls.feed = Feed.objects.create(
            feed_id='test_feed',
            is_current=True
        )
        
        # Create test agency
        cls.agency = Agency.objects.create(
            feed=cls.feed,
            agency_id='test_agency',
            agency_name='Test Transit Agency',
            agency_url='https://test.com',
            agency_timezone='America/Costa_Rica'
        )
        
        # Create test stops
        cls.stop1 = Stop.objects.create(
            feed=cls.feed,
            stop_id='stop_001',
            stop_name='Central Station',
            stop_desc='Main central bus station',
            stop_lat=9.9281,
            stop_lon=-84.0907,
            location_type=0,
            wheelchair_boarding=1
        )
        
        cls.stop2 = Stop.objects.create(
            feed=cls.feed,
            stop_id='stop_002',
            stop_name='University Stop',
            stop_desc='Near University of Costa Rica',
            stop_lat=9.9370,
            stop_lon=-84.0514,
            location_type=0,
            wheelchair_boarding=1
        )
        
        cls.stop3 = Stop.objects.create(
            feed=cls.feed,
            stop_id='stop_003',
            stop_name='Shopping Mall',
            stop_desc='Major shopping center',
            stop_lat=9.9000,
            stop_lon=-84.1000,
            location_type=0,
            wheelchair_boarding=0
        )
        
        # Create test routes
        cls.route1 = Route.objects.create(
            feed=cls.feed,
            route_id='route_001',
            agency_id='test_agency',
            _agency=cls.agency,
            route_short_name='R1',
            route_long_name='Route 1 - Downtown to Airport',
            route_desc='Express route to the airport',
            route_type=3,
            route_color='FF0000',
            route_text_color='FFFFFF'
        )
        
        cls.route2 = Route.objects.create(
            feed=cls.feed,
            route_id='route_002',
            agency_id='test_agency',
            _agency=cls.agency,
            route_short_name='R2',
            route_long_name='Route 2 - University Line',
            route_desc='University campus route',
            route_type=3,
            route_color='00FF00',
            route_text_color='000000'
        )

    def test_search_requires_query_parameter(self):
        """Test that search endpoint requires 'q' parameter."""
        resp = self.client.get('/api/search/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = resp.json()
        self.assertIn('error', data)
        self.assertIn('required', data['error'].lower())

    def test_search_stops_by_exact_name(self):
        """Test searching for stops by exact name match."""
        resp = self.client.get('/api/search/?q=Central Station&type=stops')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        self.assertEqual(data['query'], 'Central Station')
        self.assertEqual(data['results_type'], 'stops')
        self.assertEqual(data['total_results'], 1)
        
        result = data['results'][0]
        self.assertEqual(result['stop_id'], 'stop_001')
        self.assertEqual(result['stop_name'], 'Central Station')
        self.assertEqual(result['relevance_score'], 1.0)  # Exact match should get highest score
        self.assertEqual(result['result_type'], 'stop')

    def test_search_stops_by_partial_name(self):
        """Test searching for stops by partial name match."""
        resp = self.client.get('/api/search/?q=University&type=stops')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        self.assertGreaterEqual(data['total_results'], 1)
        
        # Should find the University Stop
        stop_ids = [result['stop_id'] for result in data['results']]
        self.assertIn('stop_002', stop_ids)

    def test_search_stops_by_description(self):
        """Test searching for stops by description."""
        resp = self.client.get('/api/search/?q=shopping&type=stops')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        self.assertGreaterEqual(data['total_results'], 1)
        
        # Should find the Shopping Mall stop
        stop_ids = [result['stop_id'] for result in data['results']]
        self.assertIn('stop_003', stop_ids)

    def test_search_routes_by_exact_short_name(self):
        """Test searching for routes by exact short name match."""
        resp = self.client.get('/api/search/?q=R1&type=routes')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        self.assertEqual(data['query'], 'R1')
        self.assertEqual(data['results_type'], 'routes')
        self.assertEqual(data['total_results'], 1)
        
        result = data['results'][0]
        self.assertEqual(result['route_id'], 'route_001')
        self.assertEqual(result['route_short_name'], 'R1')
        self.assertEqual(result['relevance_score'], 1.0)  # Exact match should get highest score
        self.assertEqual(result['result_type'], 'route')

    def test_search_routes_by_long_name(self):
        """Test searching for routes by long name."""
        resp = self.client.get('/api/search/?q=University Line&type=routes')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        self.assertGreaterEqual(data['total_results'], 1)
        
        # Should find Route 2
        route_ids = [result['route_id'] for result in data['results']]
        self.assertIn('route_002', route_ids)

    def test_search_routes_by_description(self):
        """Test searching for routes by description."""
        resp = self.client.get('/api/search/?q=airport&type=routes')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        self.assertGreaterEqual(data['total_results'], 1)
        
        # Should find Route 1 (has "airport" in description)
        route_ids = [result['route_id'] for result in data['results']]
        self.assertIn('route_001', route_ids)

    def test_search_all_types_default(self):
        """Test searching all types (default behavior)."""
        resp = self.client.get('/api/search/?q=Central')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        self.assertEqual(data['results_type'], 'all')
        self.assertGreater(data['total_results'], 0)
        
        # Should include both stops and routes if relevant
        result_types = [result['result_type'] for result in data['results']]
        self.assertIn('stop', result_types)  # Should find "Central Station"

    def test_search_with_limit(self):
        """Test search with limit parameter."""
        resp = self.client.get('/api/search/?q=Route&limit=1')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        self.assertLessEqual(data['total_results'], 1)

    def test_search_limit_validation(self):
        """Test search limit parameter validation."""
        # Test invalid limit (too low)
        resp = self.client.get('/api/search/?q=test&limit=0')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test invalid limit (too high)
        resp = self.client.get('/api/search/?q=test&limit=101')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test invalid limit (not integer)
        resp = self.client.get('/api/search/?q=test&limit=abc')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_invalid_type(self):
        """Test search with invalid type parameter."""
        resp = self.client.get('/api/search/?q=test&type=invalid')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        data = resp.json()
        self.assertIn('error', data)

    def test_search_with_nonexistent_feed_id(self):
        """Test search with non-existent feed_id."""
        resp = self.client.get('/api/search/?q=test&feed_id=nonexistent')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        data = resp.json()
        self.assertIn('error', data)

    def test_search_no_current_feed(self):
        """Test search behavior when no current feed is available."""
        # Set current feed to False
        Feed.objects.update(is_current=False)
        
        resp = self.client.get('/api/search/?q=test')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        data = resp.json()
        self.assertIn('error', data)
        
        # Restore current feed for other tests
        Feed.objects.update(is_current=True)

    def test_search_relevance_ranking(self):
        """Test that search results are properly ranked by relevance."""
        # Create additional stop with partial match
        Stop.objects.create(
            feed=self.feed,
            stop_id='stop_004',
            stop_name='Central Park',
            stop_desc='Small park near central area',
            stop_lat=9.9300,
            stop_lon=-84.0800,
            location_type=0,
            wheelchair_boarding=1
        )
        
        resp = self.client.get('/api/search/?q=Central&type=stops')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        # Should find both "Central Station" and "Central Park"
        self.assertGreaterEqual(data['total_results'], 2)
        
        # Results should be sorted by relevance score (highest first)
        scores = [result['relevance_score'] for result in data['results']]
        self.assertEqual(scores, sorted(scores, reverse=True))
        
        # "Central Station" should rank higher than "Central Park" for query "Central"
        first_result = data['results'][0]
        self.assertEqual(first_result['stop_name'], 'Central Station')

    def test_search_response_structure(self):
        """Test that search response has correct structure."""
        resp = self.client.get('/api/search/?q=Central')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        # Check top-level structure
        required_fields = ['query', 'results_type', 'total_results', 'results']
        for field in required_fields:
            self.assertIn(field, data)
        
        # Check results structure if any results
        if data['total_results'] > 0:
            result = data['results'][0]
            self.assertIn('relevance_score', result)
            self.assertIn('result_type', result)
            
            if result['result_type'] == 'stop':
                stop_fields = ['stop_id', 'stop_name', 'feed_id']
                for field in stop_fields:
                    self.assertIn(field, result)
            elif result['result_type'] == 'route':
                route_fields = ['route_id', 'route_type', 'feed_id']
                for field in route_fields:
                    self.assertIn(field, result)

    def test_search_empty_query(self):
        """Test search with empty or whitespace-only query."""
        resp = self.client.get('/api/search/?q=')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        
        resp = self.client.get('/api/search/?q=   ')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_search_no_results(self):
        """Test search with query that returns no results."""
        resp = self.client.get('/api/search/?q=NonexistentLocation')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        self.assertEqual(data['total_results'], 0)
        self.assertEqual(data['results'], [])

    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        # Test uppercase
        resp = self.client.get('/api/search/?q=CENTRAL&type=stops')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertGreater(data['total_results'], 0)
        
        # Test lowercase
        resp = self.client.get('/api/search/?q=central&type=stops')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertGreater(data['total_results'], 0)
        
        # Test mixed case
        resp = self.client.get('/api/search/?q=CeNtRaL&type=stops')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        self.assertGreater(data['total_results'], 0)

    def test_search_with_special_characters(self):
        """Test search handles special characters gracefully."""
        # Create stop with special characters
        Stop.objects.create(
            feed=self.feed,
            stop_id='stop_special',
            stop_name='Parada San José',
            stop_desc='Near José María Monument',
            stop_lat=9.9200,
            stop_lon=-84.0850,
            location_type=0,
            wheelchair_boarding=1
        )
        
        # Search with accented characters
        resp = self.client.get('/api/search/?q=José&type=stops')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        data = resp.json()
        
        # Should find the stop with José in name or description
        stop_ids = [result['stop_id'] for result in data['results']]
        self.assertIn('stop_special', stop_ids)

    def test_search_with_numbers_and_symbols(self):
        """Test search with numbers and symbols in query."""
        # Should not crash with numbers or symbols
        test_queries = ['R1', '123', 'route-1', 'stop@test', 'bus#1']
        
        for query in test_queries:
            resp = self.client.get(f'/api/search/?q={query}')
            # Should not return server error, but might return no results
            self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
            
    def test_search_with_very_long_query(self):
        """Test search handles very long queries appropriately."""
        long_query = 'a' * 1000  # Very long query
        
        resp = self.client.get(f'/api/search/?q={long_query}')
        # Should handle gracefully without server error
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])
        
        if resp.status_code == status.HTTP_200_OK:
            data = resp.json()
            # Results should be empty or minimal
            self.assertLessEqual(data['total_results'], 0)
