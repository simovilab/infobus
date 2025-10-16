from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken


class JWTAuthenticationTestCase(APITestCase):
    """Test JWT authentication functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'password_confirm': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        self.login_data = {
            'username': 'testuser',
            'password': 'testpass123'
        }
    
    def test_user_registration(self):
        """Test user registration endpoint"""
        url = reverse('auth-register')
        response = self.client.post(url, self.user_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['username'], 'testuser')
    
    def test_user_registration_password_mismatch(self):
        """Test registration with password mismatch"""
        invalid_data = self.user_data.copy()
        invalid_data['password_confirm'] = 'wrongpassword'
        
        url = reverse('auth-register')
        response = self.client.post(url, invalid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_user_login(self):
        """Test user login with JWT tokens"""
        # First create a user
        User.objects.create_user(**{
            'username': self.user_data['username'],
            'email': self.user_data['email'],
            'password': self.user_data['password']
        })
        
        url = reverse('auth-login')
        response = self.client.post(url, self.login_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
    
    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        url = reverse('auth-login')
        invalid_data = {
            'username': 'nonexistent',
            'password': 'wrongpass'
        }
        response = self.client.post(url, invalid_data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        # JWT returns 'detail' field for invalid credentials
        self.assertTrue('detail' in response.data or 'error' in response.data)
    
    def test_token_refresh(self):
        """Test JWT token refresh"""
        # Create user and get tokens
        user = User.objects.create_user(**{
            'username': self.user_data['username'],
            'email': self.user_data['email'],
            'password': self.user_data['password']
        })
        
        refresh = RefreshToken.for_user(user)
        
        url = reverse('auth-refresh')
        response = self.client.post(url, {'refresh': str(refresh)}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
    
    def test_user_profile_authenticated(self):
        """Test accessing user profile with valid JWT token"""
        # Create user and get token
        user = User.objects.create_user(**{
            'username': self.user_data['username'],
            'email': self.user_data['email'],
            'password': self.user_data['password']
        })
        
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # Access profile endpoint with JWT token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('auth-profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.user_data['username'])
    
    def test_user_profile_unauthenticated(self):
        """Test accessing user profile without authentication"""
        url = reverse('auth-profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_protected_endpoint_requires_auth(self):
        """Test that protected endpoints require authentication"""
        url = reverse('stop-list')  # StopViewSet requires authentication
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_protected_endpoint_with_auth(self):
        """Test that protected endpoints work with valid JWT token"""
        # Create user and get token
        user = User.objects.create_user(**{
            'username': self.user_data['username'],
            'email': self.user_data['email'],
            'password': self.user_data['password']
        })
        
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        # Access protected endpoint with JWT token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('stop-list')
        response = self.client.get(url)
        
        # Should return 200 (though might be empty list)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_public_endpoint_no_auth_required(self):
        """Test that public endpoints don't require authentication"""
        url = reverse('health')  # HealthView is public
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)