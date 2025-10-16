from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
import time


class RateLimitingTestCase(APITestCase):
    """Test rate limiting functionality for API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def get_jwt_token(self):
        """Get JWT token for authenticated requests"""
        refresh = RefreshToken.for_user(self.user)
        return str(refresh.access_token)
    
    @override_settings(RATELIMIT_ENABLE=True, RATE_LIMITS={'public_light': '3/m'})
    def test_public_light_endpoint_rate_limit(self):
        """Test rate limiting on light public endpoints (health)"""
        url = reverse('health')
        
        # Make requests up to the limit
        for i in range(3):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Next request should be rate limited
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Rate limit exceeded')
        self.assertIn('retry_after', response.data)
    
    @override_settings(RATELIMIT_ENABLE=True, RATE_LIMITS={'public_medium': '2/m'})
    def test_public_medium_endpoint_rate_limit(self):
        """Test rate limiting on medium public endpoints (arrivals)"""
        url = reverse('arrivals')
        
        # Make requests with required parameters
        params = {'stop_id': 'test-stop'}
        
        # Make requests up to the limit
        for i in range(2):
            response = self.client.get(url, params)
            # May return 400 for missing stop but should not be rate limited yet
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Next request should be rate limited
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('error', response.data)
    
    @override_settings(RATELIMIT_ENABLE=True, RATE_LIMITS={'public_heavy': '1/m'})
    def test_public_heavy_endpoint_rate_limit(self):
        """Test rate limiting on heavy public endpoints (search)"""
        url = reverse('search')
        params = {'q': 'test'}
        
        # First request should work
        response = self.client.get(url, params)
        self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Second request should be rate limited
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Rate limit exceeded')
    
    @override_settings(RATELIMIT_ENABLE=True, RATE_LIMITS={'auth_register': '1/m'})
    def test_auth_register_rate_limit(self):
        """Test rate limiting on user registration endpoint"""
        url = reverse('auth-register')
        user_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'password_confirm': 'newpass123'
        }
        
        # First registration should work
        response = self.client.post(url, user_data, format='json')
        self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Second registration attempt should be rate limited
        user_data['username'] = 'newuser2'
        user_data['email'] = 'newuser2@example.com'
        response = self.client.post(url, user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('error', response.data)
    
    @override_settings(RATELIMIT_ENABLE=True, RATE_LIMITS={'auth_sensitive': '1/m'})
    def test_auth_login_rate_limit(self):
        """Test rate limiting on login endpoint"""
        url = reverse('auth-login')
        login_data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        
        # First login should work
        response = self.client.post(url, login_data, format='json')
        self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Second login attempt should be rate limited
        response = self.client.post(url, login_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn('error', response.data)
    
    @override_settings(RATELIMIT_ENABLE=True, RATE_LIMITS={'auth_general': '2/m'})
    def test_auth_profile_rate_limit(self):
        """Test rate limiting on profile endpoint"""
        url = reverse('auth-profile')
        token = self.get_jwt_token()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        
        # Make requests up to the limit
        for i in range(2):
            response = self.client.get(url)
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Next request should be rate limited
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    
    @override_settings(RATELIMIT_ENABLE=False)
    def test_rate_limiting_disabled(self):
        """Test that rate limiting can be disabled via settings"""
        url = reverse('health')
        
        # Make many requests when rate limiting is disabled
        for i in range(10):
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            # None should be rate limited
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
    
    def test_rate_limit_error_response_format(self):
        """Test the format of rate limit error responses"""
        with override_settings(RATELIMIT_ENABLE=True, RATE_LIMITS={'public_light': '1/m'}):
            url = reverse('health')
            
            # Exhaust rate limit
            self.client.get(url)
            
            # Get rate limited response
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Verify response structure
            self.assertIn('error', response.data)
            self.assertIn('details', response.data)
            self.assertIn('retry_after', response.data)
            self.assertIn('limit_type', response.data)
            self.assertIn('timestamp', response.data)
            
            # Verify response values
            self.assertEqual(response.data['error'], 'Rate limit exceeded')
            self.assertEqual(response.data['limit_type'], 'requests_per_minute')
            self.assertIsInstance(response.data['retry_after'], int)
    
    def test_rate_limit_configuration(self):
        """Test that rate limiting configuration works correctly"""
        with override_settings(RATELIMIT_ENABLE=True, RATE_LIMITS={'public_light': '2/m'}):
            url = reverse('health')
            
            # First request should work
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Second request should work (within limit of 2/m)
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Third request should be rate limited
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            
            # Verify the error response contains the expected fields
            self.assertIn('error', response.data)
            self.assertEqual(response.data['error'], 'Rate limit exceeded')
            self.assertIn('details', response.data)
    
    def test_authenticated_vs_unauthenticated_limits(self):
        """Test that authenticated users might have different limits"""
        with override_settings(RATELIMIT_ENABLE=True, RATE_LIMITS={'auth_general': '10/m'}):
            url = reverse('auth-profile')
            
            # Unauthenticated request
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            
            # Authenticated request with rate limiting
            token = self.get_jwt_token()
            self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
            
            # Should allow more requests for authenticated users
            for i in range(5):  # Well under the limit
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)