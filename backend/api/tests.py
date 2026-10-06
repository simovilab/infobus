from unittest.mock import patch

from django.core.cache import cache, caches
from django.core.cache.backends.locmem import LocMemCache
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from rest_framework import status

from . import views


RESOURCE_BASENAMES: tuple[str, ...] = (
    "infoservice",
    "feedpublisher",
    "agency",
    "stop",
    "geo-stop",
    "shape",
    "geoshape",
    "route",
    "calendar",
    "calendardate",
    "trip",
    "stoptime",
    "fareattribute",
    "farerule",
    "feedinfo",
)

LOC_MEM_CACHE_SETTINGS: dict[str, dict[str, str]] = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "api-tests",
    },
}


READ_ONLY_VIEWSETS = (
    views.InfoServiceViewSet,
    views.FeedPublisherViewSet,
    views.AgencyViewSet,
    views.StopViewSet,
    views.GeoStopViewSet,
    views.ShapeViewSet,
    views.GeoShapeViewSet,
    views.RouteViewSet,
    views.CalendarViewSet,
    views.CalendarDateViewSet,
    views.TripViewSet,
    views.StopTimeViewSet,
    views.FareAttributeViewSet,
    views.FareRuleViewSet,
    views.FeedInfoViewSet,
)


class EmptyResourceQuerysetsMixin:
    """Replace resource querysets with empty querysets during HTTP tests."""

    def setUp(self) -> None:
        """Patch resource querysets before every test."""
        super().setUp()
        for viewset in READ_ONLY_VIEWSETS:
            self.enterContext(
                patch.object(viewset, "queryset", viewset.queryset.none())
            )


@override_settings(CACHES=LOC_MEM_CACHE_SETTINGS)
class ReadOnlyAPIViewsTests(EmptyResourceQuerysetsMixin, SimpleTestCase):
    """Verify the registered API resources remain read-only."""

    def setUp(self) -> None:
        """Clear the isolated cache before each test."""
        super().setUp()
        cache.clear()

    def tearDown(self) -> None:
        """Clear the isolated cache after each test."""
        cache.clear()
        super().tearDown()

    def test_write_methods_are_not_allowed(self) -> None:
        """Reject write methods for every registered resource."""
        for basename in RESOURCE_BASENAMES:
            list_url = reverse(f"{basename}-list")
            detail_url = reverse(f"{basename}-detail", kwargs={"pk": "missing"})

            with self.subTest(resource=basename, method="POST"):
                cache.clear()
                response = self.client.post(list_url)
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

            with self.subTest(resource=basename, method="PUT"):
                cache.clear()
                response = self.client.put(detail_url)
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

            with self.subTest(resource=basename, method="PATCH"):
                cache.clear()
                response = self.client.patch(detail_url)
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

            with self.subTest(resource=basename, method="DELETE"):
                cache.clear()
                response = self.client.delete(detail_url)
                self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_list_requests_are_successful(self) -> None:
        """Return successful responses for every registered resource list."""
        for basename in RESOURCE_BASENAMES:
            with self.subTest(resource=basename):
                response = self.client.get(reverse(f"{basename}-list"))
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_responses_are_paginated(self) -> None:
        """Return the standard pagination structure for resource lists."""
        response = self.client.get(reverse("agency-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.json()
        for key in ("count", "next", "previous", "results"):
            with self.subTest(key=key):
                self.assertIn(key, payload)
        self.assertIsInstance(payload["results"], list)


@override_settings(CACHES=LOC_MEM_CACHE_SETTINGS)
class ThrottleTests(EmptyResourceQuerysetsMixin, SimpleTestCase):
    """Verify the geometry throttle enforces its configured rate."""

    def setUp(self) -> None:
        """Clear the isolated cache before each test."""
        super().setUp()
        cache.clear()

    def tearDown(self) -> None:
        """Clear the isolated cache after each test."""
        cache.clear()
        super().tearDown()

    def test_geometry_requests_are_throttled_after_the_limit(self) -> None:
        """Allow geometry requests within the limit and reject the next request."""
        url = reverse("geo-stop-list")

        self.assertIsInstance(caches["default"], LocMemCache)
        for request_number in range(1, 11):
            with self.subTest(request_number=request_number):
                allowed_response = self.client.get(url)
                self.assertEqual(allowed_response.status_code, status.HTTP_200_OK)
        throttled_response = self.client.get(url)

        self.assertEqual(throttled_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class SchemaViewTests(SimpleTestCase):
    """Verify the schema endpoint accepts only GET requests."""

    def test_schema_view_allows_only_get(self) -> None:
        """Return a schema for GET and reject POST."""
        url = reverse("schema")

        get_response = self.client.get(url)
        post_response = self.client.post(url)

        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(post_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
