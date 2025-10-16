"""
API middleware for usage tracking and authentication
"""

import time
from django.utils.deprecation import MiddlewareMixin
from .rate_limiting import capture_api_usage


class APIUsageTrackingMiddleware(MiddlewareMixin):
    """
    Middleware to track API usage for authenticated clients
    """
    
    def process_request(self, request):
        """Record start time for response time calculation"""
        # Only track API endpoints (not admin, static files, etc.)
        if request.path.startswith('/api/'):
            request._api_start_time = time.time()
        return None
    
    def process_response(self, request, response):
        """Capture API usage metrics after response is generated"""
        # Only track API endpoints that have start time recorded
        if hasattr(request, '_api_start_time') and request.path.startswith('/api/'):
            # Extract endpoint path (remove /api/ prefix and query parameters)
            endpoint = request.path
            if endpoint.startswith('/api/'):
                endpoint = endpoint[5:]  # Remove '/api/' prefix
            
            # Capture usage metrics
            capture_api_usage(
                request=request,
                endpoint=endpoint,
                response=response,
                start_time=request._api_start_time
            )
        
        return response