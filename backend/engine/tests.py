from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import requests

from django.test import SimpleTestCase, override_settings

from engine.tasks import evaluate_run_lifecycles, get_vehicle_positions


@override_settings(RUN_LIFECYCLE_EVALUATION_LOCK_SECONDS=120)
class EvaluateRunLifecyclesTaskTests(SimpleTestCase):
    @patch("engine.tasks.evaluate_active_runs")
    @patch("engine.tasks.lifecycle_redis")
    def test_skips_overlapping_evaluation(self, redis, evaluate_active_runs):
        lock = redis.lock.return_value
        lock.acquire.return_value = False

        result = evaluate_run_lifecycles()

        self.assertEqual(result, {})
        evaluate_active_runs.assert_not_called()
        lock.release.assert_not_called()

    @patch("engine.tasks.evaluate_active_runs", return_value={"Completed": 2})
    @patch("engine.tasks.lifecycle_redis")
    def test_renews_and_releases_evaluation_lock(self, redis, evaluate_active_runs):
        lock = redis.lock.return_value
        lock.acquire.return_value = True

        result = evaluate_run_lifecycles()

        self.assertEqual(result, {"Completed": 2})
        evaluate_active_runs.assert_called_once_with(heartbeat=lock.reacquire)
        lock.release.assert_called_once_with()


class GetVehiclePositionsTaskTests(SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.transit_system_filter = self._start_patch(
            "engine.tasks.TransitSystem.objects.filter"
        )
        self.feed_publisher_filter = self._start_patch(
            "engine.tasks.FeedPublisher.objects.filter"
        )
        self.requests_get = self._start_patch("engine.tasks.requests.get")
        self.feed_message = self._start_patch("engine.tasks.gtfs_rt.FeedMessage")
        self.save_vehicle_positions = self._start_patch(
            "engine.tasks.save_vehicle_positions_to_database"
        )
        self.update_vehicle_positions_state = self._start_patch(
            "engine.tasks.update_vehicle_positions_state"
        )
        self.record_successful_poll = self._start_patch(
            "engine.tasks.record_successful_poll"
        )
        self.refresh_topics = self._start_patch(
            "engine.tasks.refresh_active_vehicle_position_topics"
        )
        self.requests_get.return_value.content = b""
        self.update_vehicle_positions_state.return_value = set()

    def _start_patch(self, target):
        patcher = patch(target)
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked

    @staticmethod
    def _queryset(items):
        queryset = MagicMock()
        queryset.exists.return_value = bool(items)
        queryset.__iter__.return_value = iter(items)
        return queryset

    def _configure_systems(self, *systems_and_publishers):
        transit_systems = []
        publisher_querysets = []
        for code, publisher_urls in systems_and_publishers:
            transit_systems.append(SimpleNamespace(code=code))
            publishers = [
                SimpleNamespace(vehicle_positions_url=url)
                for url in publisher_urls
            ]
            publisher_querysets.append(self._queryset(publishers))

        self.transit_system_filter.return_value = self._queryset(transit_systems)
        self.feed_publisher_filter.side_effect = publisher_querysets

    def test_vehicle_position_poll_refreshes_each_successful_system_once(self):
        self._configure_systems(
            ("system-a", ("https://first.example", "https://second.example"))
        )

        get_vehicle_positions()

        self.refresh_topics.assert_called_once_with("system-a")

    def test_vehicle_position_poll_refreshes_each_system_separately(self):
        self._configure_systems(
            ("zeta", ("https://zeta.example",)),
            ("alpha", ("https://alpha.example",)),
        )

        get_vehicle_positions()

        self.refresh_topics.assert_has_calls([call("alpha"), call("zeta")])
        self.assertEqual(self.refresh_topics.call_count, 2)

    def test_vehicle_position_poll_does_not_refresh_failed_publisher(self):
        self._configure_systems(("system-a", ("https://failed.example",)))
        self.requests_get.side_effect = requests.RequestException("request failed")

        get_vehicle_positions()

        self.refresh_topics.assert_not_called()
        self.record_successful_poll.assert_not_called()

    def test_vehicle_position_poll_refreshes_system_with_one_failed_publisher(self):
        self._configure_systems(
            ("system-a", ("https://failed.example", "https://success.example"))
        )
        successful_response = MagicMock()
        successful_response.content = b""
        self.requests_get.side_effect = [
            requests.RequestException("request failed"),
            successful_response,
        ]

        get_vehicle_positions()

        self.refresh_topics.assert_called_once_with("system-a")
        self.record_successful_poll.assert_called_once()

    def test_vehicle_position_refresh_failure_does_not_fail_task(self):
        self._configure_systems(("system-a", ("https://success.example",)))
        self.refresh_topics.side_effect = RuntimeError("refresh failed")

        with patch("engine.tasks.logging.exception") as logging_exception:
            result = get_vehicle_positions()

        self.assertEqual(result, "VehiclePositions have been processed")
        logging_exception.assert_called_once_with(
            "Failed to refresh active VehiclePositions topics for %s",
            "system-a",
        )

    def test_vehicle_position_poll_without_active_systems_does_not_refresh(self):
        self._configure_systems()

        result = get_vehicle_positions()

        self.assertEqual(result, "No active transit systems found.")
        self.refresh_topics.assert_not_called()


class CeleryBrokerRedisCredentialTests(SimpleTestCase):
    def test_celery_broker_url_carries_redis_credentials_when_configured(self):
        """Verifies the Celery Redis URL conditionally carries encoded credentials."""
        from django.conf import settings

        broker_url = settings.CELERY_BROKER_URL

        self.assertTrue(broker_url.startswith("redis://"))
        if settings.REDIS_PASSWORD:
            self.assertIn("@", broker_url)
            if any(
                character in settings.REDIS_PASSWORD
                for character in ":/?#[]@!$&'()*+,;=%"
            ):
                password_is_plaintext = settings.REDIS_PASSWORD in broker_url
                self.assertFalse(password_is_plaintext)
        else:
            self.assertNotIn("@", broker_url)
