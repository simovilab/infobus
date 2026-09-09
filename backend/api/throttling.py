from redis.exceptions import RedisError
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle


class ResilientThrottleMixin:
    """Fail open (don't throttle) if the cache/Redis backend is unreachable."""

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except RedisError:
            return True


class ResilientAnonRateThrottle(ResilientThrottleMixin, AnonRateThrottle):
    pass


class ResilientScopedRateThrottle(ResilientThrottleMixin, ScopedRateThrottle):
    pass
