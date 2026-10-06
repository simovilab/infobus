"""Tests for the Infobús Web backend-for-frontend endpoints."""

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status

from feed.models import Feed, FeedPublisher, Route, Stop, TransitSystem


LOC_MEM_CACHE_SETTINGS: dict[str, dict[str, str]] = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "web-tests",
    },
}


@override_settings(CACHES=LOC_MEM_CACHE_SETTINGS)
class WebBFFTestCase(TestCase):
    """Provide two active systems sharing GTFS identifiers, one inactive system, and a non-current feed."""

    @classmethod
    def setUpTestData(cls) -> None:
        """Create transit systems, publishers, feeds, routes, and stops shared by all tests."""
        cls.alpha = TransitSystem.objects.create(
            name="Alpha", code="alpha", is_active=True
        )
        cls.beta = TransitSystem.objects.create(
            name="Beta", code="beta", is_active=True
        )
        TransitSystem.objects.create(name="Gamma", code="gamma", is_active=False)

        alpha_publisher = FeedPublisher.objects.create(
            transit_system=cls.alpha,
            code="pub_alpha",
            name="Alpha Publisher",
            timezone="America/Costa_Rica",
            is_active=True,
        )
        beta_publisher = FeedPublisher.objects.create(
            transit_system=cls.beta,
            code="pub_beta",
            name="Beta Publisher",
            timezone="America/Costa_Rica",
            is_active=True,
        )

        alpha_current = Feed.objects.create(
            feed_id="alpha-current",
            feed_publisher=alpha_publisher,
            is_current=True,
            version="A2",
        )
        alpha_old = Feed.objects.create(
            feed_id="alpha-old",
            feed_publisher=alpha_publisher,
            is_current=False,
            version="A1",
        )
        beta_current = Feed.objects.create(
            feed_id="beta-current",
            feed_publisher=beta_publisher,
            is_current=True,
            version="B1",
        )

        route_fields = {"agency_id": "AG", "route_type": 3}
        Route.objects.create(
            feed=alpha_current,
            route_id="R1",
            route_short_name="1",
            route_long_name="Alpha Line",
            **route_fields,
        )
        Route.objects.create(
            feed=alpha_current,
            route_id="R.2",
            route_short_name="2",
            route_long_name="Alpha Dotted Line",
            **route_fields,
        )
        Route.objects.create(
            feed=alpha_old,
            route_id="OLD",
            route_short_name="0",
            route_long_name="Alpha Retired Line",
            **route_fields,
        )
        Route.objects.create(
            feed=beta_current,
            route_id="R1",
            route_short_name="1",
            route_long_name="Beta Line",
            **route_fields,
        )

        stop_fields = {"stop_lat": Decimal("9.93"), "stop_lon": Decimal("-84.05")}
        Stop.objects.create(
            feed=alpha_current, stop_id="S1", stop_name="Alpha Stop", **stop_fields
        )
        Stop.objects.create(
            feed=alpha_old, stop_id="S-OLD", stop_name="Alpha Retired Stop", **stop_fields
        )
        Stop.objects.create(
            feed=beta_current, stop_id="S1", stop_name="Beta Stop", **stop_fields
        )

    def setUp(self) -> None:
        """Clear the isolated cache so throttling state never leaks between tests."""
        super().setUp()
        cache.clear()

    def get_json(self, url: str, system: str | None = None) -> tuple[int, object]:
        """GET a URL, optionally selecting a transit system, and return status and JSON body."""
        if system is not None:
            url = f"{url}?system={system}"
        response = self.client.get(url)
        return response.status_code, response.json()


class RouterTests(WebBFFTestCase):
    """Verify the web router exposes the expected resources."""

    def test_root_lists_registered_resources(self) -> None:
        """List home, routes, and stops at the router root."""
        status_code, body = self.get_json(reverse("web:api-root"))

        self.assertEqual(status_code, status.HTTP_200_OK)
        self.assertEqual(set(body), {"home", "routes", "stops"})


class HomeViewTests(WebBFFTestCase):
    """Verify the Home summary and the temporary transit-system resolution rule."""

    def test_requires_system_when_several_are_active(self) -> None:
        """Reject a request without ?system= when more than one system is active."""
        status_code, body = self.get_json(reverse("web:home-list"))

        self.assertEqual(status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("system", body)

    def test_returns_only_the_selected_system(self) -> None:
        """Return the selected system with only its current feeds."""
        status_code, body = self.get_json(reverse("web:home-list"), system="alpha")

        self.assertEqual(status_code, status.HTTP_200_OK)
        self.assertEqual(body["transit_system"]["code"], "alpha")
        self.assertEqual(
            [feed["feed_id"] for feed in body["current_feeds"]], ["alpha-current"]
        )

    def test_defaults_to_the_only_active_system(self) -> None:
        """Use the only active system when ?system= is omitted."""
        TransitSystem.objects.filter(pk=self.beta.pk).update(is_active=False)

        status_code, body = self.get_json(reverse("web:home-list"))

        self.assertEqual(status_code, status.HTTP_200_OK)
        self.assertEqual(body["transit_system"]["code"], "alpha")

    def test_rejects_unknown_or_inactive_system(self) -> None:
        """Return 404 for a code that does not exist or belongs to an inactive system."""
        for code in ("missing", "gamma"):
            with self.subTest(code=code):
                status_code, _ = self.get_json(reverse("web:home-list"), system=code)
                self.assertEqual(status_code, status.HTTP_404_NOT_FOUND)


class RoutesViewTests(WebBFFTestCase):
    """Verify route listing and retrieval are scoped to the selected system's current feeds."""

    def test_list_contains_only_current_routes_of_selected_system(self) -> None:
        """List routes from the selected system's current feed, paginated."""
        status_code, body = self.get_json(reverse("web:route-list"), system="alpha")

        self.assertEqual(status_code, status.HTTP_200_OK)
        for key in ("count", "next", "previous", "results"):
            with self.subTest(key=key):
                self.assertIn(key, body)
        self.assertEqual(
            {route["route_id"] for route in body["results"]}, {"R1", "R.2"}
        )

    def test_detail_resolves_route_within_selected_system(self) -> None:
        """Return a different route for the same route_id in each system."""
        url = reverse("web:route-detail", kwargs={"route_id": "R1"})
        expected = {"alpha": "Alpha Line", "beta": "Beta Line"}

        for code, long_name in expected.items():
            with self.subTest(system=code):
                status_code, body = self.get_json(url, system=code)
                self.assertEqual(status_code, status.HTTP_200_OK)
                self.assertEqual(body["route_long_name"], long_name)

    def test_detail_accepts_identifiers_with_dots(self) -> None:
        """Retrieve a route whose GTFS identifier contains a dot."""
        url = reverse("web:route-detail", kwargs={"route_id": "R.2"})

        status_code, body = self.get_json(url, system="alpha")

        self.assertEqual(status_code, status.HTTP_200_OK)
        self.assertEqual(body["route_id"], "R.2")

    def test_detail_excludes_routes_from_non_current_feeds(self) -> None:
        """Return 404 for a route that exists only in a non-current feed."""
        url = reverse("web:route-detail", kwargs={"route_id": "OLD"})

        status_code, _ = self.get_json(url, system="alpha")

        self.assertEqual(status_code, status.HTTP_404_NOT_FOUND)

    def test_write_methods_are_not_allowed(self) -> None:
        """Reject POST on the routes list."""
        response = self.client.post(f"{reverse('web:route-list')}?system=alpha")

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class StopsViewTests(WebBFFTestCase):
    """Verify stop listing and retrieval are scoped to the selected system's current feeds."""

    def test_list_contains_only_current_stops_of_selected_system(self) -> None:
        """List stops from the selected system's current feed."""
        status_code, body = self.get_json(reverse("web:stop-list"), system="alpha")

        self.assertEqual(status_code, status.HTTP_200_OK)
        self.assertEqual([stop["stop_id"] for stop in body["results"]], ["S1"])

    def test_detail_resolves_stop_within_selected_system(self) -> None:
        """Return a different stop for the same stop_id in each system."""
        url = reverse("web:stop-detail", kwargs={"stop_id": "S1"})
        expected = {"alpha": "Alpha Stop", "beta": "Beta Stop"}

        for code, stop_name in expected.items():
            with self.subTest(system=code):
                status_code, body = self.get_json(url, system=code)
                self.assertEqual(status_code, status.HTTP_200_OK)
                self.assertEqual(body["stop_name"], stop_name)

    def test_detail_excludes_stops_from_non_current_feeds(self) -> None:
        """Return 404 for a stop that exists only in a non-current feed."""
        url = reverse("web:stop-detail", kwargs={"stop_id": "S-OLD"})

        status_code, _ = self.get_json(url, system="alpha")

        self.assertEqual(status_code, status.HTTP_404_NOT_FOUND)
