"""
Rate limiting utilities and decorators for API endpoints

This module provides two approaches for rate limiting:
1. Simple approach: Direct function calls (currently used in views)
2. Decorator approach: Function and class decorators for cleaner code
"""

import functools
from django.conf import settings
from django.http import JsonResponse
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited
from django_ratelimit.core import is_ratelimited
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
import time


# =============================================================================
# SIMPLE APPROACH (Currently used in views)
# =============================================================================

def get_rate_limit(rate_key):
    """Get rate limit setting for a given key"""
    rate_limits = getattr(settings, 'RATE_LIMITS', {})
    # Default fallbacks based on endpoint type
    defaults = {
        'public_light': '100/m',      # Health, ready endpoints
        'public_medium': '60/m',      # Arrivals, schedule endpoints
        'public_heavy': '30/m',       # Search endpoints
        'auth_register': '5/h',       # User registration
        'auth_login': '10/h',         # Login attempts
        'auth_refresh': '20/m',       # Token refresh
        'auth_profile': '60/m',       # Profile access
        'auth_sensitive': '10/h',     # Login attempts (alias)
        'auth_general': '60/m',       # General auth endpoints
        'status': '100/m',            # Status endpoint
    }
    return rate_limits.get(rate_key, defaults.get(rate_key, '60/m'))


def rate_limit_error_response():
    """Generate a 429 rate limit error response"""
    return Response({
        'error': 'Rate limit exceeded',
        'details': 'Too many requests. Please try again later.',
        'retry_after': 60,
        'limit_type': 'requests_per_minute',
        'timestamp': timezone.now().isoformat()
    }, status=status.HTTP_429_TOO_MANY_REQUESTS)


def check_rate_limit(request, group, rate_key, key='ip', method=['GET']):
    """
    Check if request is rate limited
    
    Usage in views:
        if check_rate_limit(request, 'api_search', 'public_heavy'):
            return rate_limit_error_response()
    
    Args:
        request: Django request object
        group: Rate limiting group name
        rate_key: Key from RATE_LIMITS settings dict
        key: What to rate limit by ('ip', 'user', etc.)
        method: HTTP methods to check
    
    Returns:
        bool: True if rate limited, False otherwise
    """
    if not getattr(settings, 'RATELIMIT_ENABLE', True):
        return False
        
    rate = get_rate_limit(rate_key)
    return is_ratelimited(
        request=request, 
        group=group, 
        fn=None, 
        key=key, 
        rate=rate, 
        method=method, 
        increment=True
    )


# =============================================================================
# DECORATOR APPROACH (For future use or refactoring)
# =============================================================================

def custom_ratelimited_error(request, exception):
    """
    Custom error handler for rate limited requests
    Returns a DRF Response with detailed error information
    """
    error_data = {
        'error': 'Rate limit exceeded',
        'details': 'Too many requests. Please try again later.',
        'retry_after': getattr(exception, 'retry_after', 60),
        'limit_type': 'requests_per_minute',
        'timestamp': timezone.now().isoformat()
    }
    return Response(error_data, status=status.HTTP_429_TOO_MANY_REQUESTS)


def api_ratelimit(rate_key='public_medium', key='ip', method=['GET', 'POST']):
    """
    Custom rate limiting decorator for API views
    
    Usage:
        @api_ratelimit(rate_key='public_heavy', method=['GET'])
        def my_view(request):
            return Response({'data': 'example'})
    
    Args:
        rate_key: Key from RATE_LIMITS settings dict
        key: What to rate limit by ('ip', 'user', 'header:x-real-ip')
        method: HTTP methods to rate limit
    """
    def decorator(view_func):
        # Skip rate limiting if disabled in settings
        if not getattr(settings, 'RATELIMIT_ENABLE', True):
            return view_func
            
        # Get rate from settings
        rate_limits = getattr(settings, 'RATE_LIMITS', {})
        rate = rate_limits.get(rate_key, '60/m')  # Default fallback
        
        # Apply django-ratelimit decorator directly
        @ratelimit(key=key, rate=rate, method=method, block=True)
        @functools.wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            # Check if we were rate limited
            if getattr(request, 'limited', False):
                return custom_ratelimited_error(request, None)
            return view_func(request, *args, **kwargs)
        
        return wrapped_view
    return decorator


def ratelimit_view_class(rate_key='public_medium', key='ip', methods=['GET', 'POST']):
    """
    Class decorator for Django REST framework views
    
    Usage:
        @ratelimit_view_class(rate_key='public_heavy', methods=['GET'])
        class MyAPIView(APIView):
            def get(self, request):
                return Response({'data': 'example'})
    """
    def decorator(view_class):
        # Skip rate limiting if disabled
        if not getattr(settings, 'RATELIMIT_ENABLE', True):
            return view_class
            
        # Get rate from settings
        rate_limits = getattr(settings, 'RATE_LIMITS', {})
        rate = rate_limits.get(rate_key, '60/m')
        
        # Apply ratelimit decorator to the dispatch method
        original_dispatch = view_class.dispatch
        
        # Create a properly decorated dispatch method
        @ratelimit(key=key, rate=rate, method=methods, block=True)
        def dispatch_with_ratelimit(self, request, *args, **kwargs):
            if getattr(request, 'limited', False):
                return custom_ratelimited_error(request, None)
            return original_dispatch(self, request, *args, **kwargs)
        
        view_class.dispatch = dispatch_with_ratelimit
        return view_class
    
    return decorator


def get_client_ip(request):
    """
    Get the client IP address from the request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_client_from_request(request):
    """
    Extract client from JWT token or return None for anonymous requests
    """
    # Check for JWT token in Authorization header
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
        
    try:
        # Import here to avoid circular imports
        from .models import Client
        import jwt
        
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        client_id = payload.get('client_id')
        
        if client_id:
            return Client.objects.get(id=client_id, status='active')
    except (jwt.InvalidTokenError, Client.DoesNotExist, IndexError, KeyError):
        pass
    
    return None


def capture_api_usage(request, endpoint, response, start_time=None):
    """
    Capture API usage metrics for authenticated clients
    
    Args:
        request: Django request object
        endpoint: API endpoint that was accessed
        response: Django response object
        start_time: When the request started (for response time calculation)
    """
    try:
        # Import here to avoid circular imports
        from .models import ClientUsage
        
        client = get_client_from_request(request)
        if not client:
            return  # Don't track anonymous requests
        
        # Calculate response time
        response_time_ms = None
        if start_time:
            response_time_ms = int((time.time() - start_time) * 1000)
        
        # Extract request details
        method = request.method
        status_code = response.status_code if hasattr(response, 'status_code') else 200
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]  # Truncate long user agents
        ip_address = get_client_ip(request)
        
        # Get request/response sizes
        request_size = len(request.body) if hasattr(request, 'body') and request.body else None
        response_size = None
        if hasattr(response, 'content'):
            response_size = len(response.content)
        elif hasattr(response, 'data'):
            response_size = len(str(response.data))
        
        # Capture error message for failed requests
        error_message = ''
        if status_code >= 400 and hasattr(response, 'data') and isinstance(response.data, dict):
            error_message = str(response.data.get('error', ''))[:500]
        
        # Create usage record
        ClientUsage.objects.create(
            client=client,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            user_agent=user_agent,
            ip_address=ip_address,
            request_size_bytes=request_size,
            response_size_bytes=response_size,
            error_message=error_message
        )
        
        # Update client's last_used_at timestamp
        client.last_used_at = timezone.now()
        client.save(update_fields=['last_used_at'])
        
    except Exception as e:
        # Don't let usage tracking break the API
        # In production, you might want to log this error
        print(f"Failed to capture API usage: {e}")
        pass


# =============================================================================
# CONVENIENCE DECORATORS
# =============================================================================

# Convenience decorators for common rate limiting scenarios
public_heavy_limit = functools.partial(api_ratelimit, rate_key='public_heavy')
public_medium_limit = functools.partial(api_ratelimit, rate_key='public_medium')
public_light_limit = functools.partial(api_ratelimit, rate_key='public_light')
auth_sensitive_limit = functools.partial(api_ratelimit, rate_key='auth_sensitive')
auth_register_limit = functools.partial(api_ratelimit, rate_key='auth_register')
auth_general_limit = functools.partial(api_ratelimit, rate_key='auth_general')