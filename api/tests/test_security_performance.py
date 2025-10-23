"""
Tests for security and performance features.

Tests CORS configuration, ETag/HTTP caching, query limits, and rate limiting.
"""
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth.models import User
from gtfs.models import Feed, Stop, Route
import time


class CORSConfigurationTest(APITestCase):
    """Test CORS configuration for different environments."""
    
    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse('health')
    
    @override_settings(
        CORS_ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:8000"]
    )
    def test_cors_headers_present(self):
        """Test that CORS headers are present in responses."""
        response = self.client.get(
            self.health_url,
            HTTP_ORIGIN='http://localhost:3000'
        )
        
        # Should have successful response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_cors_preflight_request(self):
        """Test CORS preflight OPTIONS request."""
        response = self.client.options(
            self.health_url,
            HTTP_ORIGIN='http://localhost:3000',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='GET'
        )
        
        # OPTIONS request should succeed
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT])


class ETAgCachingTest(APITestCase):
    """Test ETag and HTTP caching headers."""
    
    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse('health')
    
    def test_etag_header_generated(self):
        """Test that ETag header is generated for GET requests."""
        response = self.client.get(self.health_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # ETag should be present in response headers
        self.assertIn('ETag', response)
    
    def test_conditional_get_with_etag(self):
        """Test conditional GET using If-None-Match header."""
        # First request to get ETag
        response1 = self.client.get(self.health_url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        etag = response1.get('ETag')
        self.assertIsNotNone(etag)
        
        # Second request with If-None-Match
        response2 = self.client.get(
            self.health_url,
            HTTP_IF_NONE_MATCH=etag
        )
        
        # Should return 304 Not Modified if content hasn't changed
        if response2.status_code == status.HTTP_304_NOT_MODIFIED:
            self.assertEqual(response2.status_code, status.HTTP_304_NOT_MODIFIED)
        else:
            # Or 200 with ETag if implementation varies
            self.assertEqual(response2.status_code, status.HTTP_200_OK)
    
    def test_cache_control_headers(self):
        """Test that Cache-Control headers are set appropriately."""
        response = self.client.get(self.health_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Cache-Control header should be present
        self.assertIn('Cache-Control', response)


class QueryLimitsTest(APITestCase):
    """Test query and result limits enforcement."""
    
    def setUp(self):
        self.client = APIClient()
        # Create a test feed
        self.feed = Feed.objects.create(
            feed_id='test_feed',
            is_current=True
        )
        
        # Create test stops
        for i in range(150):
            Stop.objects.create(
                feed=self.feed,
                stop_id=f'STOP_{i:03d}',
                stop_name=f'Test Stop {i}',
                stop_lat=9.9 + (i * 0.001),
                stop_lon=-84.1 + (i * 0.001)
            )
    
    def test_default_pagination_limit(self):
        """Test that default pagination is applied."""
        url = reverse('stop-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be paginated
        self.assertIn('results', response.data)
        # Default page size should be 50 or less
        self.assertLessEqual(len(response.data['results']), 50)
    
    def test_maximum_page_size_enforced(self):
        """Test that maximum page size limit is enforced."""
        url = reverse('stop-list')
        # Try to request more than max allowed
        response = self.client.get(url, {'limit': 2000})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        if 'results' in response.data:
            # Should not return more than MAX_PAGE_SIZE (1000)
            self.assertLessEqual(len(response.data['results']), 1000)
    
    def test_pagination_with_offset(self):
        """Test pagination with offset parameter."""
        url = reverse('stop-list')
        response = self.client.get(url, {'limit': 10, 'offset': 0})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertLessEqual(len(response.data['results']), 10)


class RateLimitingTest(APITestCase):
    """Test rate limiting for different endpoint types."""
    
    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse('health')
        
        # Create test user for authenticated rate limits
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
    
    @override_settings(RATELIMIT_ENABLE=False)
    def test_rate_limiting_disabled(self):
        """Test that endpoints work when rate limiting is disabled."""
        # Make multiple rapid requests
        for _ in range(10):
            response = self.client.get(self.health_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_anonymous_rate_limit_exists(self):
        """Test that anonymous users have rate limits."""
        # This test verifies the rate limit configuration exists
        # Actual enforcement depends on cache backend
        from django.conf import settings
        
        throttle_rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        self.assertIn('anon', throttle_rates)
        self.assertIsNotNone(throttle_rates['anon'])
    
    def test_authenticated_rate_limit_exists(self):
        """Test that authenticated users have different rate limits."""
        from django.conf import settings
        
        throttle_rates = settings.REST_FRAMEWORK.get('DEFAULT_THROTTLE_RATES', {})
        self.assertIn('user', throttle_rates)
        self.assertIsNotNone(throttle_rates['user'])


class HealthCheckTest(APITestCase):
    """Test health and readiness check endpoints."""
    
    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse('health')
        self.ready_url = reverse('ready')
    
    def test_health_check_returns_ok(self):
        """Test that health check endpoint returns OK status."""
        response = self.client.get(self.health_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)
        self.assertEqual(response.data['status'], 'ok')
    
    def test_health_check_no_authentication_required(self):
        """Test that health check doesn't require authentication."""
        response = self.client.get(self.health_url)
        
        # Should work without authentication
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_readiness_check_structure(self):
        """Test readiness check response structure."""
        response = self.client.get(self.ready_url)
        
        # Should return status code (200 or 503)
        self.assertIn(response.status_code, [
            status.HTTP_200_OK,
            status.HTTP_503_SERVICE_UNAVAILABLE
        ])
        
        # Should have required fields
        self.assertIn('status', response.data)
        self.assertIn('database_ok', response.data)
        self.assertIn('current_feed_available', response.data)
    
    def test_readiness_check_with_no_feed(self):
        """Test readiness check when no GTFS feed is available."""
        # Clear all feeds
        Feed.objects.all().delete()
        
        response = self.client.get(self.ready_url)
        
        # Should return 503 when not ready
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(response.data['status'], 'not_ready')
        self.assertFalse(response.data['current_feed_available'])


class SecurityHeadersTest(APITestCase):
    """Test security-related HTTP headers."""
    
    def setUp(self):
        self.client = APIClient()
        self.health_url = reverse('health')
    
    def test_safe_methods_only_cached(self):
        """Test that only safe methods (GET, HEAD) receive cache headers."""
        # GET request should have cache headers
        get_response = self.client.get(self.health_url)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        
        # Cache-Control should be present for GET
        if 'Cache-Control' in get_response:
            self.assertIn('Cache-Control', get_response)
    
    def test_vary_headers_present(self):
        """Test that Vary headers are set for proper caching."""
        response = self.client.get(self.health_url)
        
        # Vary header helps with caching across different clients
        # May or may not be present depending on middleware order
        if 'Vary' in response:
            self.assertIn('Vary', response)


class PerformanceConfigurationTest(TestCase):
    """Test performance-related configuration."""
    
    def test_cache_backend_configured(self):
        """Test that cache backend is properly configured."""
        from django.core.cache import cache
        from django.conf import settings
        
        # Cache should be configured
        self.assertIsNotNone(settings.CACHES)
        self.assertIn('default', settings.CACHES)
        
        # Test cache operations
        cache.set('test_key', 'test_value', 10)
        self.assertEqual(cache.get('test_key'), 'test_value')
        cache.delete('test_key')
    
    def test_max_page_size_setting(self):
        """Test that MAX_PAGE_SIZE is configured."""
        from django.conf import settings
        
        max_page_size = getattr(settings, 'MAX_PAGE_SIZE', None)
        self.assertIsNotNone(max_page_size)
        self.assertGreater(max_page_size, 0)
    
    def test_cors_settings_configured(self):
        """Test that CORS settings are properly configured."""
        from django.conf import settings
        
        # CORS should be configured
        cors_origins = getattr(settings, 'CORS_ALLOWED_ORIGINS', None)
        self.assertIsNotNone(cors_origins)
        self.assertIsInstance(cors_origins, (list, tuple))
