from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from website.views import _projection_metadata


class UpdatesPageTests(SimpleTestCase):
    @patch("website.views._current_schedule_systems")
    def test_renders_registry_driven_console(self, current_schedule_systems):
        current_schedule_systems.return_value = [
            {
                "code": "mbta",
                "name": "MBTA",
                "stops": [{"stop_id": "123", "stop_name": "Test Stop"}],
            }
        ]

        response = self.client.get(reverse("updates_test"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Updates console")
        self.assertContains(response, "Test Stop")
        self.assertContains(response, "stop_stop_time_updates")
        self.assertContains(response, "/ws/updates/")
        self.assertContains(response, "projection.primary_selector")

    def test_stop_time_projection_metadata_includes_both_parameters(self):
        from updates.registry import PROJECTIONS

        projection = next(
            projection
            for projection in PROJECTIONS
            if projection.name == "stop_stop_time_updates"
        )

        metadata = _projection_metadata(projection)

        self.assertEqual(
            [parameter["name"] for parameter in metadata["parameters"]],
            ["stop_id", "direction_id"],
        )
        self.assertEqual(metadata["qualifier_selector"], "by_direction")

    def test_existing_stop_occupancy_is_exposed_from_registry(self):
        from updates.registry import PROJECTIONS

        projection = next(
            projection
            for projection in PROJECTIONS
            if projection.name == "stop_occupancy_status"
        )

        metadata = _projection_metadata(projection)

        self.assertEqual(metadata["info"], "occupancy_status")
        self.assertEqual(metadata["primary_selector"], "by_stop")
