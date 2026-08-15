from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch
from uuid import uuid4

from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase, override_settings

from runs.events.types import OccupancyStatusChanged
from runs.events.types import RunCompleted
from updates.builders.stop.stop_time_updates import build_stop_time_updates
from updates.consumers import UpdatesConsumer
from updates.events import parse_event
from updates.exceptions import InvalidTopicException
from updates.planner import process_event
from updates.projections.stop.occupancy_status import (
    resolve_stop_occupancy_topics,
)
from updates.projections.stop.stop_time_updates import (
    resolve_stop_time_updates_topics,
    validate_stop_time_updates_topic,
)
from updates.projections.trip.occupancy_status import (
    resolve_trip_occupancy_topics,
)
from updates.registry import projection_for_topic
from updates.topics import TopicKey


class TopicKeyTests(SimpleTestCase):
    def test_scoped_topic_round_trip(self):
        raw = "mbta.stop.occupancy_status.by_stop.123"

        topic = TopicKey.parse(raw)

        self.assertEqual(topic.transit_system, "mbta")
        self.assertEqual(topic.render(), raw)
        self.assertEqual(topic.group_name(), TopicKey.parse(raw).group_name())
        self.assertLessEqual(len(topic.group_name()), 100)

    def test_rejects_unscoped_topic(self):
        raw = "stop.occupancy_status.by_stop.123"

        with self.assertRaises(InvalidTopicException) as context:
            TopicKey.parse(raw)

        self.assertEqual(context.exception.topic, raw)
        self.assertEqual(
            context.exception.reason,
            "A topic must have 5 or 7 segments.",
        )

    def test_rejects_non_string_topic(self):
        with self.assertRaises(InvalidTopicException) as context:
            TopicKey.parse(123)  # type: ignore[arg-type]

        self.assertEqual(context.exception.topic, 123)
        self.assertEqual(context.exception.reason, "A topic must be a string.")

    def test_qualified_topic_round_trip(self):
        raw = "mbta.stop.stop_time_updates.by_stop.123.by_direction.1"

        topic = TopicKey.parse(raw)

        self.assertEqual(topic.qualifier_selector, "by_direction")
        self.assertEqual(topic.qualifier_value, "1")
        self.assertEqual(topic.render(), raw)


class UpdatesConsumerTests(SimpleTestCase):
    async def test_connect_sends_json_acknowledgement(self):
        communicator = WebsocketCommunicator(
            UpdatesConsumer.as_asgi(),
            "/ws/updates/",
        )

        connected, _ = await communicator.connect()

        self.assertTrue(connected)
        self.assertEqual(
            await communicator.receive_json_from(),
            {"type": "connected"},
        )
        await communicator.disconnect()

    async def test_binary_message_returns_protocol_error(self):
        communicator = WebsocketCommunicator(
            UpdatesConsumer.as_asgi(),
            "/ws/updates/",
        )
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_to(bytes_data=b"unsupported")

        self.assertEqual(
            await communicator.receive_json_from(),
            {
                "type": "error",
                "message": "Binary WebSocket messages are not supported.",
            },
        )
        await communicator.disconnect()

    @patch("updates.consumers.validate_topic")
    async def test_invalid_projection_value_is_rejected_before_subscribe(
        self,
        validate_topic,
    ):
        raw_topic = "mbta.stop.stop_time_updates.by_stop.123.by_direction.2"
        validate_topic.side_effect = InvalidTopicException(
            raw_topic,
            "direction_id must be the canonical GTFS value 0 or 1.",
        )
        communicator = WebsocketCommunicator(
            UpdatesConsumer.as_asgi(),
            "/ws/updates/",
        )
        await communicator.connect()
        await communicator.receive_json_from()

        await communicator.send_json_to({"action": "subscribe", "topic": raw_topic})

        response = await communicator.receive_json_from()
        self.assertEqual(response["type"], "error")
        self.assertIn("direction_id", response["message"])
        await communicator.disconnect()


class EventParsingTests(SimpleTestCase):
    def test_first_observation_can_omit_previous_state(self):
        event = parse_event(
            {
                "transit_system": "mbta",
                "event_id": str(uuid4()),
                "event_type": "OccupancyStatusChanged",
                "run_id": str(uuid4()),
                "current_state": "1",
            }
        )

        self.assertIsInstance(event, OccupancyStatusChanged)
        self.assertIsNone(event.previous_state)
        self.assertEqual(event.current_state, 1)

    def test_parses_lifecycle_event_without_projection(self):
        event = parse_event(
            {
                "transit_system": "mbta",
                "event_id": str(uuid4()),
                "event_type": "RunCompleted",
                "run_id": str(uuid4()),
                "reason": "Reached the terminal.",
                "occurred_at": "2026-08-02T12:00:00Z",
            }
        )

        self.assertEqual(event.event_type, "RunCompleted")


class OccupancyProjectionTests(SimpleTestCase):
    def setUp(self):
        self.event = OccupancyStatusChanged(
            transit_system="mbta",
            run_id=uuid4(),
            current_state=1,
        )

    def test_resolves_direct_trip_topic(self):
        topics = resolve_trip_occupancy_topics(self.event)

        self.assertEqual(
            topics[0].render(),
            f"mbta.trip.occupancy_status.by_run.{self.event.run_id}",
        )

    @patch(
        "updates.projections.stop.occupancy_status.remaining_stop_ids",
        return_value=["A", "B"],
    )
    def test_resolves_all_remaining_stop_topics(self, remaining_stop_ids):
        topics = resolve_stop_occupancy_topics(self.event)

        remaining_stop_ids.assert_called_once_with("mbta", self.event.run_id)
        self.assertEqual(
            [topic.render() for topic in topics],
            [
                "mbta.stop.occupancy_status.by_stop.A",
                "mbta.stop.occupancy_status.by_stop.B",
            ],
        )

    def test_terminal_event_resolves_affected_stop_topics(self):
        event = RunCompleted(
            transit_system="mbta",
            run_id=uuid4(),
            reason="Reached terminal.",
            occurred_at="2026-08-02T12:00:00Z",
            affected_stop_ids_json='["A", "B"]',
        )

        topics = resolve_stop_occupancy_topics(event)

        self.assertEqual(
            [topic.primary_value for topic in topics],
            ["A", "B"],
        )


class StopTimeUpdatesProjectionTests(SimpleTestCase):
    def test_registry_resolves_required_qualified_topic(self):
        projection = projection_for_topic(
            TopicKey.parse("mbta.stop.stop_time_updates.by_stop.X.by_direction.1")
        )

        self.assertIsNotNone(projection)
        self.assertEqual(projection.name, "stop_stop_time_updates")

    def test_rejects_non_gtfs_direction(self):
        topic = TopicKey.parse("mbta.stop.stop_time_updates.by_stop.X.by_direction.01")

        with self.assertRaises(InvalidTopicException):
            validate_stop_time_updates_topic(topic)

    @patch("updates.builders.stop.stop_time_updates.Run.objects.filter")
    @patch(
        "updates.builders.stop.stop_time_updates.approaching_run_ids",
        return_value=[],
    )
    @patch("updates.builders.stop.stop_time_updates.r")
    def test_builder_returns_valid_empty_snapshot(
        self,
        redis,
        _approaching_run_ids,
        filter_runs,
    ):
        redis.smembers.return_value = set()
        filter_runs.return_value.select_related.return_value = []
        topic = TopicKey.parse(
            "mbta.stop.stop_time_updates.by_stop.EMPTY.by_direction.1"
        )

        snapshot = build_stop_time_updates(topic)

        self.assertEqual(snapshot["stop_time_updates"], [])
        self.assertEqual(snapshot["stop_id"], "EMPTY")
        self.assertEqual(snapshot["direction_id"], 1)

    @patch("updates.projections.stop.stop_time_updates.Run.objects.filter")
    def test_lifecycle_resolver_uses_run_direction_and_affected_stops(
        self,
        filter_runs,
    ):
        filter_runs.return_value.values_list.return_value.first.return_value = 1
        event = RunCompleted(
            transit_system="mbta",
            run_id=uuid4(),
            reason="Reached terminal.",
            occurred_at="2026-08-02T12:00:00Z",
            affected_stop_ids_json='["A", "B", "A"]',
        )

        topics = resolve_stop_time_updates_topics(event)

        self.assertEqual(
            [topic.render() for topic in topics],
            [
                "mbta.stop.stop_time_updates.by_stop.A.by_direction.1",
                "mbta.stop.stop_time_updates.by_stop.B.by_direction.1",
            ],
        )
        filter_runs.assert_called_once_with(
            id=event.run_id,
            feed_publisher__transit_system__code="mbta",
        )

    @patch("updates.builders.stop.stop_time_updates._current_documents")
    @patch(
        "updates.builders.stop.stop_time_updates.timezone.now",
        return_value=datetime(1970, 1, 1, tzinfo=UTC),
    )
    @patch(
        "updates.builders.stop.stop_time_updates.run_is_approaching_stop",
        return_value=True,
    )
    @patch("updates.builders.stop.stop_time_updates.approaching_run_ids")
    @patch("updates.builders.stop.stop_time_updates.Run.objects.filter")
    @patch("updates.builders.stop.stop_time_updates.r")
    def test_builder_uses_current_state_preserves_visits_and_sorts(
        self,
        redis,
        filter_runs,
        approaching_run_ids,
        _run_is_approaching_stop,
        _now,
        current_documents,
    ):
        run_a_id = uuid4()
        run_b_id = uuid4()
        transit_system = SimpleNamespace(code="mbta")
        publisher = SimpleNamespace(transit_system=transit_system)
        run_a = SimpleNamespace(
            id=run_a_id,
            trip_id="trip-a",
            route_id="route-a",
            direction_id=1,
            feed_publisher=publisher,
        )
        run_b = SimpleNamespace(
            id=run_b_id,
            trip_id="trip-b",
            route_id="route-b",
            direction_id=1,
            feed_publisher=publisher,
        )
        filter_runs.return_value.select_related.return_value = [run_a, run_b]
        approaching_run_ids.return_value = [str(run_a_id), str(run_b_id)]
        redis.smembers.return_value = {str(run_a_id), str(run_b_id)}
        current_documents.return_value = (
            [
                [
                    {
                        "stop_id": "X",
                        "stop_sequence": 8,
                        "arrival": {},
                        "departure": {"time": 100},
                        "schedule_relationship": "SCHEDULED",
                    }
                ],
                [
                    {
                        "stop_id": "X",
                        "stop_sequence": 4,
                        "arrival": {"time": 50},
                        "departure": {},
                    },
                    {
                        "stop_id": "X",
                        "stop_sequence": 9,
                        "arrival": {"time": 200, "delay": 5},
                        "departure": {},
                        "schedule_relationship": 0,
                    },
                    {
                        "stop_id": "X",
                        "stop_sequence": 10,
                        "arrival": {"time": 300},
                        "departure": {},
                        "schedule_relationship": "SKIPPED",
                    },
                ],
            ],
            [None, 5],
        )
        topic = TopicKey.parse("mbta.stop.stop_time_updates.by_stop.X.by_direction.1")

        snapshot = build_stop_time_updates(topic)

        self.assertEqual(snapshot["topic"], topic.render())
        self.assertEqual(snapshot["direction_id"], 1)
        self.assertEqual(
            [update["run_id"] for update in snapshot["stop_time_updates"]],
            [str(run_a_id), str(run_b_id)],
        )
        self.assertEqual(
            [update["stop_sequence"] for update in snapshot["stop_time_updates"]],
            [8, 9],
        )
        self.assertEqual(
            snapshot["stop_time_updates"][0]["schedule_relationship"],
            "SCHEDULED",
        )


@override_settings(GTFS_RT_STOP_TIME_UPDATE_PAST_TOLERANCE_SECONDS=120)
class StopTimeUpdatesBuilderRegressionTests(SimpleTestCase):
    now_timestamp = 1_800_000_000

    def _run(
        self,
        *,
        route_id: str = "route-a",
        direction_id: int = 1,
        transit_system: str = "mbta",
    ) -> SimpleNamespace:
        return SimpleNamespace(
            id=uuid4(),
            trip_id=f"trip-{route_id}",
            route_id=route_id,
            direction_id=direction_id,
            feed_publisher=SimpleNamespace(
                transit_system=SimpleNamespace(code=transit_system)
            ),
        )

    def _snapshot(
        self,
        runs: list[SimpleNamespace],
        documents: dict[str, list[dict[str, object]]],
        *,
        current_sequences: dict[str, int | None] | None = None,
        active_ids: set[str] | None = None,
        candidate_ids: list[str] | None = None,
        approaching_ids: set[str] | None = None,
        transit_system: str = "mbta",
        stop_id: str = "X",
        direction_id: int = 1,
    ) -> dict[str, Any]:
        run_ids = [str(run.id) for run in runs]
        active_ids = set(run_ids) if active_ids is None else active_ids
        candidate_ids = run_ids if candidate_ids is None else candidate_ids
        approaching_ids = (
            set(candidate_ids) if approaching_ids is None else approaching_ids
        )
        current_sequences = current_sequences or {}

        with (
            patch("updates.builders.stop.stop_time_updates.r") as redis,
            patch(
                "updates.builders.stop.stop_time_updates.Run.objects.filter"
            ) as filter_runs,
            patch(
                "updates.builders.stop.stop_time_updates.approaching_run_ids",
                return_value=candidate_ids,
            ),
            patch(
                "updates.builders.stop.stop_time_updates.run_is_approaching_stop",
                side_effect=lambda _system, run_id, _stop: (
                    str(run_id) in approaching_ids
                ),
            ),
            patch(
                "updates.builders.stop.stop_time_updates._current_documents"
            ) as current_documents,
            patch(
                "updates.builders.stop.stop_time_updates.timezone.now",
                return_value=datetime.fromtimestamp(self.now_timestamp, tz=UTC),
            ),
        ):
            redis.smembers.return_value = active_ids
            filter_runs.return_value.select_related.return_value = runs
            current_documents.side_effect = lambda _system, selected_ids: (
                [documents.get(run_id, []) for run_id in selected_ids],
                [current_sequences.get(run_id) for run_id in selected_ids],
            )
            topic = TopicKey.parse(
                f"{transit_system}.stop.stop_time_updates.by_stop.{stop_id}."
                f"by_direction.{direction_id}"
            )
            return build_stop_time_updates(topic)

    def test_active_future_arrival_appears_with_gtfs_fields(self):
        run = self._run()
        documents = {
            str(run.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 4,
                    "arrival": {
                        "time": self.now_timestamp + 30,
                        "delay": 7,
                        "uncertainty": 3,
                    },
                    "departure": {"time": self.now_timestamp + 45},
                    "schedule_relationship": "SCHEDULED",
                }
            ]
        }

        snapshot = self._snapshot([run], documents)

        update = snapshot["stop_time_updates"][0]
        self.assertEqual(update["arrival"]["delay"], 7)
        self.assertEqual(update["arrival"]["uncertainty"], 3)
        self.assertEqual(update["schedule_relationship"], "SCHEDULED")

    def test_origin_departure_with_null_arrival_appears(self):
        run = self._run()
        documents = {
            str(run.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 1,
                    "arrival": {"time": None},
                    "departure": {"time": self.now_timestamp + 30},
                }
            ]
        }

        snapshot = self._snapshot([run], documents)

        update = snapshot["stop_time_updates"][0]
        self.assertIsNone(update["arrival"]["time"])
        self.assertEqual(update["departure"]["time"], self.now_timestamp + 30)

    def test_historical_timestamp_is_excluded_but_tolerance_boundary_remains(self):
        run = self._run()
        documents = {
            str(run.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 4,
                    "arrival": {"time": self.now_timestamp - 121},
                },
                {
                    "stop_id": "X",
                    "stop_sequence": 5,
                    "arrival": {"time": self.now_timestamp - 120},
                },
                {
                    "stop_id": "X",
                    "stop_sequence": 6,
                    "arrival": {"time": self.now_timestamp - 10},
                },
            ]
        }

        snapshot = self._snapshot([run], documents)

        self.assertEqual(
            [item["stop_sequence"] for item in snapshot["stop_time_updates"]],
            [5, 6],
        )

    def test_noncanonical_approaching_run_is_excluded(self):
        run = self._run()

        snapshot = self._snapshot(
            [run],
            {},
            active_ids=set(),
            candidate_ids=[str(run.id)],
        )

        self.assertEqual(snapshot["stop_time_updates"], [])

    def test_run_whose_stop_was_passed_is_excluded(self):
        run = self._run()

        snapshot = self._snapshot(
            [run],
            {},
            approaching_ids=set(),
        )

        self.assertEqual(snapshot["stop_time_updates"], [])

    def test_other_transit_system_is_excluded(self):
        valid = self._run(route_id="valid")
        other_system = self._run(route_id="foreign", transit_system="other")
        documents = {
            str(run.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 2,
                    "arrival": {"time": self.now_timestamp + 30},
                }
            ]
            for run in (valid, other_system)
        }

        snapshot = self._snapshot(
            [valid, other_system],
            documents,
        )

        self.assertEqual(
            [item["route_id"] for item in snapshot["stop_time_updates"]],
            ["valid"],
        )

    def test_other_direction_is_excluded(self):
        valid = self._run(route_id="valid")
        other_direction = self._run(route_id="opposite", direction_id=0)
        documents = {
            str(run.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 2,
                    "arrival": {"time": self.now_timestamp + 30},
                }
            ]
            for run in (valid, other_direction)
        }

        snapshot = self._snapshot([valid, other_direction], documents)

        self.assertEqual(
            [item["route_id"] for item in snapshot["stop_time_updates"]],
            ["valid"],
        )

    def test_multiple_routes_and_repeated_stop_visits_are_preserved(self):
        first = self._run(route_id="route-a")
        second = self._run(route_id="route-b")
        documents = {
            str(first.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 2,
                    "arrival": {"time": self.now_timestamp + 20},
                },
                {
                    "stop_id": "X",
                    "stop_sequence": 8,
                    "arrival": {"time": self.now_timestamp + 80},
                },
            ],
            str(second.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 3,
                    "arrival": {"time": self.now_timestamp + 30},
                }
            ],
        }

        snapshot = self._snapshot([first, second], documents)

        self.assertEqual(
            [item["route_id"] for item in snapshot["stop_time_updates"]],
            ["route-a", "route-b", "route-a"],
        )
        self.assertEqual(
            [item["stop_sequence"] for item in snapshot["stop_time_updates"]],
            [2, 3, 8],
        )

    def test_sorts_by_effective_time_keeps_unknown_last_and_hides_skipped(self):
        arrival = self._run(route_id="arrival")
        departure = self._run(route_id="departure")
        unknown = self._run(route_id="unknown")
        skipped = self._run(route_id="skipped")
        documents = {
            str(arrival.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 2,
                    "arrival": {"time": self.now_timestamp + 20},
                }
            ],
            str(departure.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 1,
                    "arrival": {"time": None},
                    "departure": {"time": self.now_timestamp + 10},
                }
            ],
            str(unknown.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 3,
                    "arrival": {},
                    "departure": {},
                }
            ],
            str(skipped.id): [
                {
                    "stop_id": "X",
                    "stop_sequence": 4,
                    "arrival": {"time": self.now_timestamp + 5},
                    "schedule_relationship": "SKIPPED",
                }
            ],
        }

        snapshot = self._snapshot(
            [arrival, departure, unknown, skipped],
            documents,
        )

        self.assertEqual(
            [item["route_id"] for item in snapshot["stop_time_updates"]],
            ["departure", "arrival", "unknown"],
        )


class PollRefreshTests(SimpleTestCase):
    @patch("updates.refresh.dispatch")
    @patch("updates.refresh.projection_for_topic")
    @patch("updates.refresh.has_subscribers")
    @patch("updates.refresh.active_subscription_topics")
    def test_refreshes_only_active_matching_topics_with_subscribers(
        self,
        active_topics,
        has_subscribers,
        projection_for_topic_mock,
        dispatch,
    ):
        from updates.refresh import refresh_active_stop_time_update_topics

        direction_zero = "mbta.stop.stop_time_updates.by_stop.A.by_direction.0"
        direction_one = "mbta.stop.stop_time_updates.by_stop.A.by_direction.1"
        active_topics.return_value = {
            direction_zero,
            direction_one,
            "mbta.stop.occupancy_status.by_stop.A",
            "other.stop.stop_time_updates.by_stop.A.by_direction.1",
        }
        has_subscribers.side_effect = lambda _redis, topic: topic == direction_one
        projection = SimpleNamespace(
            name="stop_stop_time_updates",
            validate_topic=Mock(),
            build=Mock(return_value={"stop_time_updates": []}),
        )
        occupancy_projection = SimpleNamespace(name="stop_occupancy_status")
        projection_for_topic_mock.side_effect = lambda topic: (
            occupancy_projection if topic.info == "occupancy_status" else projection
        )

        count = refresh_active_stop_time_update_topics("mbta")

        self.assertEqual(count, 1)
        projection.build.assert_called_once_with(TopicKey.parse(direction_one))
        dispatch.assert_called_once_with(
            TopicKey.parse(direction_one),
            {"stop_time_updates": []},
        )

    @patch("updates.refresh.dispatch")
    @patch("updates.refresh.projection_for_topic")
    @patch("updates.refresh.has_subscribers", return_value=True)
    @patch("updates.refresh.active_subscription_topics")
    def test_one_broken_topic_does_not_block_other_refreshes(
        self,
        active_topics,
        _has_subscribers,
        projection_for_topic_mock,
        dispatch,
    ):
        from updates.refresh import refresh_active_stop_time_update_topics

        broken = "mbta.stop.stop_time_updates.by_stop.A.by_direction.1"
        healthy = "mbta.stop.stop_time_updates.by_stop.B.by_direction.1"
        active_topics.return_value = {broken, healthy}
        projection = SimpleNamespace(
            name="stop_stop_time_updates",
            validate_topic=Mock(),
            build=Mock(side_effect=[RuntimeError("broken builder"), {"ok": True}]),
        )
        projection_for_topic_mock.return_value = projection

        count = refresh_active_stop_time_update_topics("mbta")

        self.assertEqual(count, 1)
        dispatch.assert_called_once_with(
            TopicKey.parse(healthy),
            {"ok": True},
        )


class PlannerTests(SimpleTestCase):
    @patch("updates.planner.dispatch")
    @patch("updates.planner.projections_for_event")
    def test_builds_and_dispatches_each_affected_topic(
        self,
        projections_for_event,
        dispatch,
    ):
        event = OccupancyStatusChanged(
            transit_system="mbta",
            run_id=uuid4(),
            current_state=1,
        )
        topic = TopicKey.parse("mbta.stop.occupancy_status.by_stop.A")
        projection = SimpleNamespace(
            resolve_topics=Mock(return_value=[topic]),
            build=Mock(return_value={"runs": []}),
        )
        projections_for_event.return_value = (projection,)

        process_event(event)

        projection.resolve_topics.assert_called_once_with(event)
        projection.build.assert_called_once_with(topic)
        dispatch.assert_called_once_with(topic, {"runs": []})
