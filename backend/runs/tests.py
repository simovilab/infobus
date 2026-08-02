from datetime import UTC, datetime, timedelta

from django.test import SimpleTestCase, override_settings

from runs.domain.lifecycle import RunLifecycleStates
from runs.services.lifecycle import LifecycleEvidence, decide_run_lifecycle


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
