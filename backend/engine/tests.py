from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from engine.tasks import evaluate_run_lifecycles


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
