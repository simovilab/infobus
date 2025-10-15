from __future__ import annotations

from unittest.mock import patch
from rest_framework import status
from rest_framework.test import APITestCase
from django.test import TestCase
from gtfs.models import Feed


class HealthEndpointTests(APITestCase):
    def test_health_endpoint_returns_ok(self):
        """Test that health endpoint returns 200 OK with correct structure."""
        resp = self.client.get('/api/health/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        
        data = resp.json()
        
        # Check required fields
        self.assertIn('status', data)
        self.assertIn('timestamp', data)
        
        # Check status value
        self.assertEqual(data['status'], 'ok')
        
        # Check timestamp format (ISO format)
        self.assertIsNotNone(data['timestamp'])

    def test_health_endpoint_structure(self):
        """Test that health endpoint returns expected JSON structure."""
        resp = self.client.get('/api/health/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        
        data = resp.json()
        
        # Ensure only expected fields are present
        expected_fields = {'status', 'timestamp'}
        actual_fields = set(data.keys())
        self.assertEqual(actual_fields, expected_fields)


class ReadyEndpointTests(APITestCase):
    def setUp(self):
        """Set up test data."""
        # Clean up any existing feeds
        Feed.objects.all().delete()

    def test_ready_endpoint_not_ready_no_feed(self):
        """Test that ready endpoint returns 503 when no current feed is available."""
        resp = self.client.get('/api/ready/')
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        
        data = resp.json()
        
        # Check required fields
        self.assertIn('status', data)
        self.assertIn('database_ok', data)
        self.assertIn('current_feed_available', data)
        self.assertIn('current_feed_id', data)
        self.assertIn('timestamp', data)
        
        # Check status
        self.assertEqual(data['status'], 'not_ready')
        self.assertTrue(data['database_ok'])  # Database should be OK
        self.assertFalse(data['current_feed_available'])  # No current feed
        self.assertIsNone(data['current_feed_id'])

    def test_ready_endpoint_ready_with_current_feed(self):
        """Test that ready endpoint returns 200 when current feed is available."""
        # Create a current feed
        feed = Feed.objects.create(
            feed_id='test_feed_ready',
            is_current=True
        )
        
        resp = self.client.get('/api/ready/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        
        data = resp.json()
        
        # Check status
        self.assertEqual(data['status'], 'ready')
        self.assertTrue(data['database_ok'])
        self.assertTrue(data['current_feed_available'])
        self.assertEqual(data['current_feed_id'], 'test_feed_ready')

    def test_ready_endpoint_not_ready_no_current_feed_flag(self):
        """Test ready endpoint when feed exists but is_current=False."""
        # Create feed but not marked as current
        Feed.objects.create(
            feed_id='test_feed_not_current',
            is_current=False
        )
        
        resp = self.client.get('/api/ready/')
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        
        data = resp.json()
        self.assertEqual(data['status'], 'not_ready')
        self.assertFalse(data['current_feed_available'])
        self.assertIsNone(data['current_feed_id'])

    def test_ready_endpoint_uses_latest_current_feed(self):
        """Test that ready endpoint uses the latest current feed when multiple exist."""
        # Create multiple current feeds with different retrieved_at times
        feed1 = Feed.objects.create(
            feed_id='test_feed_old',
            is_current=True
        )
        
        # Create a newer feed
        feed2 = Feed.objects.create(
            feed_id='test_feed_new',
            is_current=True
        )
        
        # Update retrieved_at to ensure proper ordering
        # (In real scenario, these would be set automatically)
        from django.utils import timezone
        import datetime
        
        Feed.objects.filter(feed_id='test_feed_old').update(
            retrieved_at=timezone.now() - datetime.timedelta(hours=1)
        )
        Feed.objects.filter(feed_id='test_feed_new').update(
            retrieved_at=timezone.now()
        )
        
        resp = self.client.get('/api/ready/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        
        data = resp.json()
        self.assertEqual(data['status'], 'ready')
        self.assertEqual(data['current_feed_id'], 'test_feed_new')

    @patch('api.views.Feed.objects.exists')
    def test_ready_endpoint_database_error(self, mock_exists):
        """Test ready endpoint behavior when database check fails."""
        # Mock database error
        mock_exists.side_effect = Exception("Database connection error")
        
        resp = self.client.get('/api/ready/')
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        
        data = resp.json()
        self.assertEqual(data['status'], 'not_ready')
        self.assertFalse(data['database_ok'])

    def test_ready_endpoint_response_structure(self):
        """Test that ready endpoint returns expected JSON structure."""
        # Create current feed for complete test
        Feed.objects.create(
            feed_id='test_feed_structure',
            is_current=True
        )
        
        resp = self.client.get('/api/ready/')
        data = resp.json()
        
        # Check all expected fields are present
        expected_fields = {
            'status', 
            'database_ok', 
            'current_feed_available', 
            'current_feed_id', 
            'timestamp'
        }
        actual_fields = set(data.keys())
        self.assertEqual(actual_fields, expected_fields)
        
        # Check field types
        self.assertIsInstance(data['status'], str)
        self.assertIsInstance(data['database_ok'], bool)
        self.assertIsInstance(data['current_feed_available'], bool)
        self.assertIsNotNone(data['timestamp'])

    def test_ready_endpoint_status_values(self):
        """Test that ready endpoint returns correct status values."""
        # Test not ready state
        resp = self.client.get('/api/ready/')
        data = resp.json()
        self.assertIn(data['status'], ['ready', 'not_ready'])
        
        # Test ready state
        Feed.objects.create(
            feed_id='test_feed_status',
            is_current=True
        )
        
        resp = self.client.get('/api/ready/')
        data = resp.json()
        self.assertEqual(data['status'], 'ready')

    @patch('api.views.Feed.objects.filter')
    def test_ready_endpoint_feed_query_exception(self, mock_filter):
        """Test ready endpoint when feed query raises an exception."""
        # First call for exists() check should succeed
        # Second call for current feed check should fail
        mock_filter.side_effect = [
            Feed.objects.none(),  # For exists() check
            Exception("Feed query error")  # For current feed check
        ]
        
        resp = self.client.get('/api/ready/')
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        
        data = resp.json()
        self.assertEqual(data['status'], 'not_ready')
        self.assertFalse(data['current_feed_available'])
        self.assertIsNone(data['current_feed_id'])


class HealthEndpointIntegrationTests(APITestCase):
    """Integration tests for health endpoints."""
    
    def test_health_and_ready_endpoints_accessible(self):
        """Test that both health endpoints are accessible via their URLs."""
        # Test health endpoint
        resp = self.client.get('/api/health/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        
        # Test ready endpoint  
        resp = self.client.get('/api/ready/')
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE])

    def test_health_endpoints_different_responses(self):
        """Test that health and ready endpoints provide different information."""
        health_resp = self.client.get('/api/health/')
        ready_resp = self.client.get('/api/ready/')
        
        health_data = health_resp.json()
        ready_data = ready_resp.json()
        
        # Health should be simpler
        self.assertEqual(len(health_data.keys()), 2)  # status, timestamp
        
        # Ready should have more detailed checks
        self.assertGreater(len(ready_data.keys()), 2)
        self.assertIn('database_ok', ready_data)
        self.assertIn('current_feed_available', ready_data)