"""
Cache decorators for API views.

Provides easy-to-use decorators for adding cache headers to API endpoints.
Uses Django's built-in cache infrastructure with ConditionalGetMiddleware.
"""
from functools import wraps
from django.views.decorators.cache import cache_control
from django.views.decorators.http import etag as django_etag
from django.utils.cache import patch_cache_control
import hashlib


def cache_api_response(timeout=60, public=True):
    """
    Decorator to add Cache-Control headers to API responses.
    
    Args:
        timeout: Cache timeout in seconds (default: 60)
        public: Whether cache is public or private (default: True)
    
    Usage:
        @cache_api_response(timeout=300)
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)
            
            # Only cache safe methods
            if request.method in ('GET', 'HEAD'):
                if public:
                    patch_cache_control(response, public=True, max_age=timeout)
                else:
                    patch_cache_control(response, private=True, max_age=timeout)
                
                # Add Vary headers for proper caching
                if not response.has_header('Vary'):
                    response['Vary'] = 'Accept, Accept-Encoding'
            
            return response
        return wrapper
    return decorator


def cache_static_data(view_func):
    """
    Decorator for static GTFS data (stops, routes, etc).
    Caches for 5 minutes.
    """
    return cache_api_response(timeout=300, public=True)(view_func)


def cache_realtime_data(view_func):
    """
    Decorator for real-time data (arrivals, positions, etc).
    Caches for 30 seconds.
    """
    return cache_api_response(timeout=30, public=True)(view_func)


def generate_etag(content):
    """
    Generate an ETag from response content.
    
    Args:
        content: Response content (bytes or string)
    
    Returns:
        ETag string
    """
    if isinstance(content, str):
        content = content.encode('utf-8')
    return f'"{hashlib.md5(content).hexdigest()}"'


# Convenience decorators combining cache and ETag
def cache_with_etag(timeout=60):
    """
    Decorator that adds both cache headers and ETag support.
    
    Combines cache_control with ETag generation for optimal caching.
    Requires ConditionalGetMiddleware to be enabled.
    """
    def decorator(view_func):
        @cache_api_response(timeout=timeout)
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
