"""
Middleware for HTTP caching and ETag support.

Provides conditional GET support and cache control headers for API responses.
"""
import hashlib
from django.utils.cache import patch_cache_control, patch_vary_headers
from django.http import HttpResponseNotModified


class ETagCacheMiddleware:
    """
    Middleware to add ETag and Cache-Control headers to safe HTTP methods.
    
    Only applies caching to GET and HEAD requests (safe methods).
    Generates ETags based on response content for conditional requests.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only cache safe methods (GET, HEAD)
        if request.method not in ("GET", "HEAD"):
            return response

        # Skip caching for specific paths
        if self._should_skip_cache(request.path):
            return response

        # Add Cache-Control headers
        self._add_cache_headers(response, request)

        # Add ETag and handle conditional GET
        if hasattr(response, "content") and response.status_code == 200:
            response = self._handle_etag(request, response)

        return response

    def _should_skip_cache(self, path):
        """Determine if caching should be skipped for this path."""
        skip_patterns = [
            "/admin/",
            "/api-auth/",
            "/ws/",
            "/health/",
            "/ready/",
        ]
        return any(path.startswith(pattern) for pattern in skip_patterns)

    def _add_cache_headers(self, response, request):
        """Add appropriate Cache-Control headers."""
        # For API endpoints, use shorter cache times
        if request.path.startswith("/api/"):
            # Schedule and static data can be cached longer
            if any(x in request.path for x in ["/stops/", "/routes/", "/shapes/", "/agencies/"]):
                cache_time = 300  # 5 minutes for static GTFS data
            # Real-time data should have shorter cache
            elif any(x in request.path for x in ["/next-trips/", "/arrivals/", "/vehicle-positions/"]):
                cache_time = 30  # 30 seconds for real-time data
            else:
                cache_time = 60  # 1 minute default

            patch_cache_control(
                response,
                public=True,
                max_age=cache_time,
                s_maxage=cache_time,
            )
            # Add Vary header for proper caching with different clients
            patch_vary_headers(response, ["Accept", "Authorization"])
        
        return response

    def _handle_etag(self, request, response):
        """Generate and check ETags for conditional GET support."""
        # Generate ETag from response content
        content = response.content
        etag = f'"{hashlib.md5(content).hexdigest()}"'
        
        # Check If-None-Match header
        if_none_match = request.META.get("HTTP_IF_NONE_MATCH")
        
        if if_none_match == etag:
            # Content hasn't changed, return 304 Not Modified
            response = HttpResponseNotModified()
        else:
            # Add ETag header to response
            response["ETag"] = etag
        
        return response
