from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from website.views import _projection_metadata


@override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
class StaticAssetsTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        static_root = cls.enterClassContext(TemporaryDirectory())
        cls.enterClassContext(override_settings(STATIC_ROOT=static_root))
        call_command("collectstatic", interactive=False, verbosity=0, stdout=StringIO())

    def test_landing_page_uses_same_origin_bootstrap_assets(self):
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        for path in (
            "/static/vendor/bootstrap/5.3.3/css/bootstrap.min.css",
            "/static/vendor/bootstrap/5.3.3/js/bootstrap.bundle.min.js",
            "/static/vendor/bootstrap-icons/1.11.3/font/bootstrap-icons.min.css",
            "/static/img/infobus.png",
        ):
            self.assertContains(response, path)
        self.assertNotContains(response, "cdn.jsdelivr.net")

    def test_status_template_uses_local_assets(self):
        html = render_to_string("status.html")

        self.assertIn("/static/vendor/bootstrap/5.3.3/css/bootstrap.min.css", html)
        self.assertIn("/static/vendor/bootstrap/5.3.3/js/bootstrap.bundle.min.js", html)
        self.assertIn(
            "/static/vendor/bootstrap-icons/1.11.3/font/bootstrap-icons.min.css", html
        )
        self.assertIn("/static/img/b.png", html)
        self.assertNotIn("cdn.jsdelivr.net", html)
        self.assertNotIn("kit.fontawesome.com", html)

    def test_whitenoise_serves_collected_assets_with_debug_disabled(self):
        assets = {
            "img/infobus.png": "image/png",
            "img/b.png": "image/png",
            "favicon.ico": "image/x-icon",
            "admin/css/base.css": "text/css",
            "vendor/bootstrap/5.3.3/css/bootstrap.min.css": "text/css",
            "vendor/bootstrap/5.3.3/js/bootstrap.bundle.min.js": "text/javascript",
            "vendor/bootstrap-icons/1.11.3/font/bootstrap-icons.min.css": "text/css",
            "vendor/bootstrap-icons/1.11.3/font/fonts/bootstrap-icons.woff": "application/font-woff",
            "vendor/bootstrap-icons/1.11.3/font/fonts/bootstrap-icons.woff2": "font/woff2",
        }
        for path, content_type in assets.items():
            with self.subTest(path=path):
                response = self.client.get(f"/static/{path}")
                self.addCleanup(response.close)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"].split(";")[0], content_type)
                self.assertEqual(response["X-Content-Type-Options"], "nosniff")


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
