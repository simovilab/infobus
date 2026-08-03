from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse


class UpdatesPageTests(SimpleTestCase):
    @patch("website.views.Stop.objects.filter")
    def test_renders_mbta_stops(self, filter_stops):
        filter_stops.return_value.exclude.return_value.order_by.return_value.values.return_value.distinct.return_value = [
            {"stop_id": "123", "stop_name": "Test Stop"}
        ]

        response = self.client.get(reverse("updates_test"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Stop")
        self.assertContains(
            response,
            "${transitSystem}.stop.occupancy_status.by_stop.${stopSelect.value}",
        )
        filter_stops.assert_called_once_with(
            feed__is_current=True,
            feed__feed_publisher__transit_system__code="mbta",
        )
