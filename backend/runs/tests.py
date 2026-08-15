from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from google.transit import gtfs_realtime_pb2 as gtfs_rt

from runs.domain.lifecycle import RunLifecycleStates
from runs.services.lifecycle import LifecycleEvidence, decide_run_lifecycle
from runs.services.state import update_trip_updates_state


@override_settings(
    RUN_NO_SIGNAL_AFTER_SECONDS=120,
    RUN_TERMINAL_SILENCE_GRACE_SECONDS=120,
    RUN_EXPECTED_END_GRACE_SECONDS=900,
    RUN_UNKNOWN_TIMEOUT_SECONDS=1800,
)
class RunLifecyclePolicyTests(SimpleTestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)

    def test_does_not_age_runs_during_feed_outage(self):
        decision = decide_run_lifecycle(
            RunLifecycleStates.IN_PROGRESS.value,
            LifecycleEvidence(
                last_seen_at=self.now - timedelta(hours=1),
                feed_healthy=False,
            ),
            self.now,
        )

        self.assertIsNone(decision)

    def test_marks_unseen_run_no_signal(self):
        decision = decide_run_lifecycle(
            RunLifecycleStates.IN_PROGRESS.value,
            LifecycleEvidence(
                last_seen_at=self.now - timedelta(minutes=3),
                feed_healthy=True,
                expected_end_at=self.now + timedelta(hours=1),
            ),
            self.now,
        )

        self.assertEqual(decision.state, RunLifecycleStates.NO_SIGNAL.value)

    def test_completes_run_stopped_at_terminal(self):
        decision = decide_run_lifecycle(
            RunLifecycleStates.IN_PROGRESS.value,
            LifecycleEvidence(
                last_seen_at=self.now - timedelta(minutes=3),
                feed_healthy=True,
                at_terminal_stop=True,
            ),
            self.now,
        )

        self.assertEqual(decision.state, RunLifecycleStates.COMPLETED.value)

    def test_completes_silent_run_near_terminal_after_expected_end(self):
        decision = decide_run_lifecycle(
            RunLifecycleStates.NO_SIGNAL.value,
            LifecycleEvidence(
                last_seen_at=self.now - timedelta(minutes=20),
                feed_healthy=True,
                near_terminal_stop=True,
                expected_end_at=self.now - timedelta(minutes=16),
            ),
            self.now,
        )

        self.assertEqual(decision.state, RunLifecycleStates.COMPLETED.value)

    def test_interrupts_run_far_from_terminal_after_expected_end(self):
        decision = decide_run_lifecycle(
            RunLifecycleStates.NO_SIGNAL.value,
            LifecycleEvidence(
                last_seen_at=self.now - timedelta(minutes=20),
                feed_healthy=True,
                near_terminal_stop=False,
                expected_end_at=self.now - timedelta(minutes=16),
            ),
            self.now,
        )

        self.assertEqual(decision.state, RunLifecycleStates.INTERRUPTED.value)

    def test_interrupts_unscheduled_run_after_long_silence(self):
        decision = decide_run_lifecycle(
            RunLifecycleStates.NO_SIGNAL.value,
            LifecycleEvidence(
                last_seen_at=self.now - timedelta(minutes=31),
                feed_healthy=True,
            ),
            self.now,
        )

        self.assertEqual(decision.state, RunLifecycleStates.INTERRUPTED.value)


class TripUpdatesStateTests(SimpleTestCase):
    @patch("runs.services.state.sync_remaining_stops")
    @patch("runs.services.state.confirm_run")
    @patch("runs.services.state.r")
    def test_preserves_presence_and_schedule_relationship_name(
        self,
        redis,
        confirm_run,
        sync_remaining_stops,
    ):
        run_id = uuid4()
        confirm_run.return_value = run_id
        feed_publisher = SimpleNamespace(transit_system=SimpleNamespace(code="mbta"))
        message = gtfs_rt.FeedMessage()
        entity = message.entity.add()
        entity.trip_update.trip.trip_id = "trip-1"
        first = entity.trip_update.stop_time_update.add()
        first.stop_id = "A"
        first.stop_sequence = 0
        first.arrival.delay = 0
        first.arrival.time = 123
        first.schedule_relationship = 1
        second = entity.trip_update.stop_time_update.add()
        second.stop_id = "B"

        observed = update_trip_updates_state(feed_publisher, message)

        self.assertEqual(observed, {run_id})
        state = redis.json.return_value.set.call_args.args[2]
        self.assertEqual(state[0]["stop_sequence"], 0)
        self.assertEqual(state[0]["arrival"]["delay"], 0)
        self.assertEqual(state[0]["schedule_relationship"], "SKIPPED")
        self.assertIsNone(state[1]["stop_sequence"])
        self.assertEqual(
            state[1]["arrival"],
            {"delay": None, "time": None, "uncertainty": None},
        )
        sync_remaining_stops.assert_called_once()
