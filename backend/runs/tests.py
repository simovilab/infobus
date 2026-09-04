from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from google.transit import gtfs_realtime_pb2 as gtfs_rt

from runs.domain.lifecycle import RunLifecycleStates
from runs.services.lifecycle import (
    LifecycleEvidence,
    _apply_redis_transition,
    decide_run_lifecycle,
    record_successful_poll,
    transition_run,
)
from runs.services.state import update_trip_updates_state
from runs.services.stop_index import ensure_remaining_stops


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
    @patch("runs.services.state.confirm_run_record")
    @patch("runs.services.state.r")
    def test_preserves_presence_and_schedule_relationship_name(
        self,
        redis,
        confirm_run_record,
        sync_remaining_stops,
    ):
        run_id = uuid4()
        confirm_run_record.return_value = SimpleNamespace(
            id=run_id,
            run_lifecycle_state=RunLifecycleStates.IN_PROGRESS.value,
        )
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

    @patch("runs.services.state.sync_remaining_stops")
    @patch("runs.services.state.confirm_run_record")
    @patch("runs.services.state.r")
    def test_terminal_run_cannot_restore_trip_update_state(
        self,
        redis,
        confirm_run_record,
        sync_remaining_stops,
    ):
        run_id = uuid4()
        confirm_run_record.return_value = SimpleNamespace(
            id=run_id,
            run_lifecycle_state=RunLifecycleStates.COMPLETED.value,
        )
        feed_publisher = SimpleNamespace(transit_system=SimpleNamespace(code="mbta"))
        message = gtfs_rt.FeedMessage()
        entity = message.entity.add()
        entity.trip_update.trip.trip_id = "historical-trip"
        update = entity.trip_update.stop_time_update.add()
        update.stop_id = "A"
        update.stop_sequence = 1
        update.arrival.time = 123

        observed = update_trip_updates_state(feed_publisher, message)

        self.assertEqual(observed, {run_id})
        sync_remaining_stops.assert_not_called()
        redis.json.return_value.set.assert_not_called()


@override_settings(RUN_TERMINAL_STATE_TTL_SECONDS=86400)
class RunLifecycleRedisCleanupTests(SimpleTestCase):
    @patch("runs.services.stop_index.Feed.objects")
    @patch("runs.services.stop_index.Run.objects")
    @patch("runs.services.stop_index.r")
    def test_terminal_run_cannot_reinitialize_remaining_stops_from_schedule(
        self,
        redis,
        run_objects,
        feed_objects,
    ):
        run_id = uuid4()
        redis.exists.return_value = False
        run_objects.filter.return_value.first.return_value = SimpleNamespace(
            id=run_id,
            trip_id="historical-trip",
            run_lifecycle_state=RunLifecycleStates.COMPLETED.value,
            schedule_relationship="SCHEDULED",
        )

        ensure_remaining_stops("mbta", run_id)

        feed_objects.filter.assert_not_called()
        redis.pipeline.assert_not_called()

    @patch("runs.services.lifecycle._apply_redis_transition")
    @patch("runs.services.lifecycle.Run.objects")
    @patch("runs.services.lifecycle.r")
    def test_successful_poll_reconciles_observed_terminal_run(
        self,
        redis,
        run_objects,
        apply_redis_transition,
    ):
        run_id = uuid4()
        run = SimpleNamespace(
            id=run_id,
            run_lifecycle_state=RunLifecycleStates.COMPLETED.value,
            schedule_relationship=None,
        )
        run_objects.filter.return_value.select_related.return_value = [run]
        feed_publisher = SimpleNamespace(
            pk=1,
            transit_system=SimpleNamespace(code="mbta"),
        )
        observed_at = datetime(2026, 8, 14, 12, tzinfo=UTC)

        record_successful_poll(
            feed_publisher,
            "trip_updates",
            [run_id],
            observed_at=observed_at,
        )

        apply_redis_transition.assert_called_once_with(
            run,
            publish_event=False,
        )
        redis.pipeline.return_value.__enter__.return_value.execute.assert_called_once_with()

    @patch("runs.services.lifecycle.transaction.on_commit")
    @patch("runs.services.lifecycle.transaction.atomic")
    @patch("runs.services.lifecycle.Run.objects")
    @patch("runs.services.lifecycle.r")
    def test_redis_cleanup_is_registered_after_lifecycle_lock_is_released(
        self,
        redis,
        run_objects,
        atomic,
        on_commit,
    ):
        events: list[str] = []

        class RecordingContext:
            def __init__(self, name: str):
                self.name = name

            def __enter__(self):
                events.append(f"{self.name}_enter")

            def __exit__(self, *_args):
                events.append(f"{self.name}_exit")

        run = SimpleNamespace(
            id=uuid4(),
            run_lifecycle_state=RunLifecycleStates.IN_PROGRESS.value,
            last_event_at=None,
            last_seen_at=None,
            missing_since=None,
            ended_at=None,
            completion_reason=None,
            save=Mock(),
        )
        redis.lock.return_value = RecordingContext("lock")
        atomic.return_value = RecordingContext("atomic")
        run_objects.select_for_update.return_value.select_related.return_value.get.return_value = run
        on_commit.side_effect = lambda _callback: events.append("on_commit")

        changed = transition_run(
            run.id,
            RunLifecycleStates.COMPLETED.value,
            "Reached terminal.",
        )

        self.assertTrue(changed)
        self.assertEqual(
            events,
            [
                "lock_enter",
                "atomic_enter",
                "atomic_exit",
                "lock_exit",
                "on_commit",
            ],
        )

    @patch("runs.services.lifecycle.r")
    def test_terminal_cleanup_removes_indexes_without_global_scan(self, redis):
        run_id = uuid4()
        redis.zrange.return_value = ["A", "B"]
        pipe = redis.pipeline.return_value.__enter__.return_value
        run = SimpleNamespace(
            id=run_id,
            run_lifecycle_state=RunLifecycleStates.COMPLETED.value,
            feed_publisher=SimpleNamespace(transit_system=SimpleNamespace(code="mbta")),
        )

        _apply_redis_transition(run, publish_event=False)

        redis.scan_iter.assert_not_called()
        pipe.srem.assert_any_call("mbta:runs:active", str(run_id))
        pipe.srem.assert_any_call(
            "mbta:stop:A:approaching_runs",
            str(run_id),
        )
        pipe.srem.assert_any_call(
            "mbta:stop:B:approaching_runs",
            str(run_id),
        )
        pipe.delete.assert_any_call(f"mbta:run:{run_id}:remaining_stops")
        pipe.set.assert_any_call(
            f"mbta:run:{run_id}:remaining_stops_initialized",
            "terminal",
            ex=86400,
        )
        pipe.expire.assert_any_call(
            f"mbta:trip:{run_id}:stop_time_updates",
            86400,
        )
        pipe.execute.assert_called_once_with()


class RunServiceRedisClientTests(SimpleTestCase):
    def test_run_service_clients_use_configured_credentials_and_decoding_modes(self):
        """Verifies credentials and decoding modes for Redis clients in run services."""
        from django.conf import settings

        from runs.services import lifecycle, realtime, state, stop_index

        clients = {
            "runs.services.realtime": (realtime.r, False),
            "runs.services.stop_index": (stop_index.r, True),
            "runs.services.lifecycle": (lifecycle.r, True),
            "runs.services.state": (state.r, False),
        }

        for module_name, (client, decodes_responses) in clients.items():
            with self.subTest(module=module_name):
                connection_kwargs = client.connection_pool.connection_kwargs
                password_is_configured = connection_kwargs["password"] == (
                    settings.REDIS_PASSWORD or None
                )

                self.assertTrue(password_is_configured)
                if decodes_responses:
                    self.assertIs(connection_kwargs.get("decode_responses"), True)
                else:
                    self.assertFalse(
                        connection_kwargs.get("decode_responses", False)
                    )
