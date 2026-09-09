import io
import zipfile
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from feed.models import Agency, Feed, FeedPublisher, Route, Stop, StopTime, TransitSystem, Trip
from feed.services.schedule import ScheduleImportError, save_schedule_to_database


def build_schedule_archive(members: dict[str, str]) -> bytes:
    """Build an in-memory GTFS Schedule archive from CSV members."""
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as schedule_zip:
        for name, content in members.items():
            schedule_zip.writestr(name, content)
    return archive.getvalue()


def build_minimal_schedule_members() -> dict[str, str]:
    """Build the smallest CSV set accepted by the required GTFS models."""
    return {
        "agency.txt": (
            "agency_id,agency_name,agency_url,agency_timezone\n"
            "agency,Test Agency,https://agency.example,America/Costa_Rica\n"
        ),
        "stops.txt": "stop_id,stop_name\nstop,Test Stop\n",
        "routes.txt": "route_id,agency_id,route_type\nroute,agency,3\n",
        "trips.txt": (
            "route_id,service_id,trip_id,direction_id,wheelchair_accessible,"
            "bikes_allowed\nroute,weekday,trip,0,0,0\n"
        ),
        "stop_times.txt": (
            "trip_id,stop_id,stop_sequence,pickup_type,drop_off_type\n"
            "trip,stop,1,0,0\n"
        ),
    }


class ScheduleImportTests(TestCase):
    """Exercise atomic GTFS Schedule imports."""

    def setUp(self) -> None:
        transit_system = TransitSystem.objects.create(
            name="Test Transit System",
            code="test-system",
            is_active=True,
        )
        self.feed_publisher = FeedPublisher.objects.create(
            transit_system=transit_system,
            code="test-publisher",
            name="Test Publisher",
            schedule_url="https://publisher.example/schedule.zip",
            timezone="America/Costa_Rica",
            is_active=True,
        )
        self.previous_etag = '"previous-etag"'
        self.new_etag = '"new-etag"'
        self.last_modified = "Mon, 01 Jan 2024 00:00:00 GMT"
        self.previous_feed = Feed.objects.create(
            feed_id="test-publisher (2023-12-31 00:00:00 UTC)",
            feed_publisher=self.feed_publisher,
            http_etag=self.previous_etag,
            http_last_modified=timezone.now(),
            is_current=True,
        )

    def _headers(self, etag: str) -> dict[str, str]:
        return {"ETag": etag, "Last-Modified": self.last_modified}

    def test_missing_required_member_writes_nothing(self) -> None:
        members = build_minimal_schedule_members()
        del members["stop_times.txt"]
        archive = build_schedule_archive(members)
        result = {"has_new_feed": {}}

        with (
            patch(
                "feed.services.schedule.requests.head",
                return_value=Mock(headers=self._headers(self.new_etag)),
            ),
            patch(
                "feed.services.schedule.requests.get",
                return_value=Mock(content=archive),
            ),
            self.assertRaises(ScheduleImportError) as raised,
        ):
            save_schedule_to_database(self.feed_publisher, result)

        self.assertIn("stop_times.txt", str(raised.exception))
        self.assertEqual(Feed.objects.count(), 1)
        self.previous_feed.refresh_from_db()
        self.assertTrue(self.previous_feed.is_current)
        self.assertEqual(self.previous_feed.http_etag, self.previous_etag)

    def test_failure_mid_import_rolls_back_everything(self) -> None:
        archive = build_schedule_archive(build_minimal_schedule_members())
        result = {"has_new_feed": {}}

        with (
            patch(
                "feed.services.schedule.requests.head",
                return_value=Mock(headers=self._headers(self.new_etag)),
            ),
            patch(
                "feed.services.schedule.requests.get",
                return_value=Mock(content=archive),
            ),
            patch.object(
                Trip.objects,
                "bulk_create",
                side_effect=RuntimeError("Trip import failed."),
            ),
            self.assertRaises(RuntimeError),
        ):
            save_schedule_to_database(self.feed_publisher, result)

        self.assertEqual(Feed.objects.count(), 1)
        self.previous_feed.refresh_from_db()
        self.assertTrue(self.previous_feed.is_current)
        self.assertEqual(self.previous_feed.http_etag, self.previous_etag)
        self.assertEqual(Agency.objects.count(), 0)
        self.assertEqual(Stop.objects.count(), 0)
        self.assertEqual(Route.objects.count(), 0)

    def test_successful_import_activates_new_feed(self) -> None:
        archive = build_schedule_archive(build_minimal_schedule_members())
        result = {"has_new_feed": {}}

        with (
            patch(
                "feed.services.schedule.requests.head",
                return_value=Mock(headers=self._headers(self.new_etag)),
            ),
            patch(
                "feed.services.schedule.requests.get",
                return_value=Mock(content=archive),
            ),
        ):
            save_schedule_to_database(self.feed_publisher, result)

        new_feed = Feed.objects.get(http_etag=self.new_etag)
        self.assertTrue(new_feed.is_current)
        self.previous_feed.refresh_from_db()
        self.assertFalse(self.previous_feed.is_current)
        self.assertEqual(Agency.objects.filter(feed=new_feed).count(), 1)
        self.assertEqual(Stop.objects.filter(feed=new_feed).count(), 1)
        self.assertEqual(Route.objects.filter(feed=new_feed).count(), 1)
        self.assertEqual(Trip.objects.filter(feed=new_feed).count(), 1)
        self.assertEqual(StopTime.objects.filter(feed=new_feed).count(), 1)
        self.assertTrue(result["has_new_feed"][self.feed_publisher.code])

    def test_unchanged_etag_skips_import(self) -> None:
        result = {"has_new_feed": {}}

        with (
            patch(
                "feed.services.schedule.requests.head",
                return_value=Mock(headers=self._headers(self.previous_etag)),
            ),
            patch("feed.services.schedule.requests.get") as get,
        ):
            save_schedule_to_database(self.feed_publisher, result)

        get.assert_not_called()
        self.assertEqual(Feed.objects.count(), 1)
        self.assertFalse(result["has_new_feed"][self.feed_publisher.code])
