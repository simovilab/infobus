from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, call, patch
from uuid import UUID, uuid4

from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase, override_settings
from pydantic import ValidationError

from runs.events.types import OccupancyStatusChanged
from runs.events.types import RunCompleted
from updates.builders.route.vehicle_positions import build_route_vehicle_positions
from updates.builders.stop.stop_time_updates import build_stop_time_updates
from updates.consumers import UpdatesConsumer
from updates.events import parse_event
from updates.exceptions import InvalidTopicException
from updates.planner import process_event
from updates.projections.route.vehicle_positions import (
    resolve_vehicle_positions_topics,
    validate_vehicle_positions_topic,
)
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
from updates.registry import projection_for_topic, projections_for_event
from updates.schemas import VehiclePositionSnapshot, VehiclePositionsByRouteSnapshot
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


class VehiclePositionSchemaTests(SimpleTestCase):
    def test_vehicle_position_snapshot_accepts_full_payload(self):
        run_id = uuid4()

        snapshot = VehiclePositionSnapshot(
            run_id=run_id,
            trip_id="trip-a",
            route_id="route-a",
            direction_id=1,
            latitude=9.934739,
            longitude=-84.087502,
            bearing=180.0,
            speed=12.5,
            odometer=5432.1,
            current_stop_sequence=4,
            stop_id="stop-a",
            current_status=2,
            congestion_level=1,
            occupancy_status=3,
            occupancy_percentage=65,
            timestamp=1_800_000_000,
        )

        self.assertEqual(snapshot.model_dump(mode="json")["run_id"], str(run_id))

    def test_vehicle_position_snapshot_accepts_null_optional_fields(self):
        snapshot = VehiclePositionSnapshot(
            run_id=uuid4(),
            trip_id=None,
            route_id="route-a",
            direction_id=None,
            latitude=9.934739,
            longitude=-84.087502,
            bearing=None,
            speed=None,
            odometer=None,
            current_stop_sequence=None,
            stop_id=None,
            current_status=None,
            congestion_level=None,
            occupancy_status=None,
            occupancy_percentage=None,
            timestamp=None,
        )

        self.assertIsNone(snapshot.trip_id)

    def test_vehicle_position_snapshot_rejects_unknown_field(self):
        with self.assertRaises(ValidationError):
            VehiclePositionSnapshot(
                run_id=uuid4(),
                trip_id=None,
                route_id="route-a",
                direction_id=None,
                latitude=9.934739,
                longitude=-84.087502,
                bearing=None,
                speed=None,
                odometer=None,
                current_stop_sequence=None,
                stop_id=None,
                current_status=None,
                congestion_level=None,
                occupancy_status=None,
                occupancy_percentage=None,
                timestamp=None,
                unknown_field="unexpected",
            )

    def test_vehicle_position_snapshot_requires_coordinates(self):
        with self.assertRaises(ValidationError):
            VehiclePositionSnapshot(
                run_id=uuid4(),
                trip_id=None,
                route_id="route-a",
                direction_id=None,
                longitude=-84.087502,
                bearing=None,
                speed=None,
                odometer=None,
                current_stop_sequence=None,
                stop_id=None,
                current_status=None,
                congestion_level=None,
                occupancy_status=None,
                occupancy_percentage=None,
                timestamp=None,
            )

    def test_vehicle_positions_by_route_snapshot_accepts_empty_vehicle_list(self):
        snapshot = VehiclePositionsByRouteSnapshot(
            topic="mbta.route.vehicle_positions.by_route.route-a",
            route_id="route-a",
            vehicles=[],
        )

        self.assertEqual(snapshot.model_dump(mode="json")["vehicles"], [])


@override_settings(GTFS_RT_VEHICLE_POSITION_STALE_TOLERANCE_SECONDS=120)
class RouteVehiclePositionsBuilderTests(SimpleTestCase):
    now_timestamp: int = 1_800_000_000

    def _scalar_keys(self, run_id: str) -> list[str]:
        return [
            f"mbta:trip:{run_id}:{field}"
            for field in (
                "current_stop_sequence",
                "stop_id",
                "current_status",
                "congestion_level",
                "occupancy_status",
                "occupancy_percentage",
                "timestamp",
            )
        ]

    def _run(
        self,
        *,
        run_id: UUID | None = None,
        route_id: str = "route-a",
        transit_system: str = "mbta",
        trip_id: str | None = "trip-a",
        direction_id: int | None = 1,
        lifecycle_state: str = "In Progress",
    ) -> SimpleNamespace:
        return SimpleNamespace(
            id=run_id or uuid4(),
            trip_id=trip_id,
            route_id=route_id,
            direction_id=direction_id,
            run_lifecycle_state=lifecycle_state,
            feed_publisher=SimpleNamespace(
                transit_system=SimpleNamespace(code=transit_system)
            ),
        )

    def _snapshot(
        self,
        runs: list[SimpleNamespace],
        positions: dict[str, dict[str, str]],
        *,
        scalars: dict[str, dict[str, str]] | None = None,
        active_ids: set[str] | None = None,
        transit_system: str = "mbta",
        route_id: str = "route-a",
        pipeline_values: list[object] | None = None,
    ) -> tuple[dict[str, Any], Mock, Mock, Mock]:
        run_ids = [str(run.id) for run in runs]
        canonical_ids = set(run_ids) if active_ids is None else active_ids
        scalars = scalars or {}

        with (
            patch("updates.builders.route.vehicle_positions.r") as redis,
            patch(
                "updates.builders.route.vehicle_positions.Run.objects.filter"
            ) as filter_runs,
            patch(
                "updates.builders.route.vehicle_positions.timezone.now",
                return_value=datetime.fromtimestamp(self.now_timestamp, tz=UTC),
            ),
        ):
            filter_runs.return_value.only.return_value.order_by.return_value = runs
            pipeline = redis.pipeline.return_value.__enter__.return_value
            if pipeline_values is None:
                pipeline_values = [
                    [run_id in canonical_ids for run_id in run_ids],
                    *[positions.get(run_id, {}) for run_id in run_ids],
                    *[
                        [
                            scalars.get(run_id, {}).get(field)
                            for field in (
                                "current_stop_sequence",
                                "stop_id",
                                "current_status",
                                "congestion_level",
                                "occupancy_status",
                                "occupancy_percentage",
                                "timestamp",
                            )
                        ]
                        for run_id in run_ids
                    ],
                ]
            pipeline.execute.return_value = pipeline_values
            topic = TopicKey.parse(
                f"{transit_system}.route.vehicle_positions.by_route.{route_id}"
            )
            snapshot = build_route_vehicle_positions(topic)
        return snapshot, redis, filter_runs, pipeline

    def test_returns_empty_snapshot_when_route_has_no_active_runs(self):
        snapshot, redis, _filter_runs, _pipeline = self._snapshot([], {})

        self.assertEqual(snapshot["vehicles"], [])
        self.assertEqual(
            snapshot["topic"], "mbta.route.vehicle_positions.by_route.route-a"
        )
        self.assertEqual(snapshot["route_id"], "route-a")
        redis.pipeline.assert_not_called()

    def test_excludes_run_absent_from_canonical_active_set(self):
        run = self._run()

        snapshot, _redis, _filter_runs, _pipeline = self._snapshot(
            [run],
            {
                str(run.id): {
                    "latitude": "9.93",
                    "longitude": "-84.08",
                }
            },
            active_ids=set(),
        )

        self.assertEqual(snapshot["vehicles"], [])

    def test_excludes_position_without_latitude(self):
        run = self._run()

        snapshot, _redis, _filter_runs, _pipeline = self._snapshot(
            [run],
            {str(run.id): {"longitude": "-84.08"}},
        )

        self.assertEqual(snapshot["vehicles"], [])

    def test_excludes_position_without_longitude(self):
        run = self._run()

        snapshot, _redis, _filter_runs, _pipeline = self._snapshot(
            [run],
            {str(run.id): {"latitude": "9.93"}},
        )

        self.assertEqual(snapshot["vehicles"], [])

    def test_excludes_stale_timestamp_but_keeps_boundary(self):
        stale = self._run()
        boundary = self._run()
        positions = {
            str(run.id): {"latitude": "9.93", "longitude": "-84.08"}
            for run in (stale, boundary)
        }
        scalars = {
            str(stale.id): {"timestamp": str(self.now_timestamp - 121)},
            str(boundary.id): {"timestamp": str(self.now_timestamp - 120)},
        }

        snapshot, _redis, _filter_runs, _pipeline = self._snapshot(
            [stale, boundary],
            positions,
            scalars=scalars,
        )

        self.assertEqual(
            [vehicle["run_id"] for vehicle in snapshot["vehicles"]],
            [str(boundary.id)],
        )

    def test_keeps_position_without_timestamp(self):
        run = self._run()

        snapshot, _redis, _filter_runs, _pipeline = self._snapshot(
            [run],
            {
                str(run.id): {
                    "latitude": "9.93",
                    "longitude": "-84.08",
                }
            },
        )

        self.assertEqual(len(snapshot["vehicles"]), 1)
        self.assertIsNone(snapshot["vehicles"][0]["timestamp"])

    def test_scopes_runs_to_transit_system_code(self):
        valid = self._run()
        foreign = self._run(transit_system="other")
        positions = {
            str(run.id): {"latitude": "9.93", "longitude": "-84.08"}
            for run in (valid, foreign)
        }

        snapshot, _redis, filter_runs, _pipeline = self._snapshot(
            [valid],
            positions,
            active_ids={str(valid.id), str(foreign.id)},
        )

        self.assertEqual(
            [vehicle["run_id"] for vehicle in snapshot["vehicles"]],
            [str(valid.id)],
        )
        filter_runs.assert_called_once_with(
            route_id="route-a",
            feed_publisher__transit_system__code="mbta",
            run_lifecycle_state__in={"In Progress", "No Signal"},
        )

    def test_excludes_runs_in_terminal_lifecycle_states(self):
        terminal = self._run(lifecycle_state="Completed")

        snapshot, redis, filter_runs, _pipeline = self._snapshot(
            [],
            {
                str(terminal.id): {
                    "latitude": "9.93",
                    "longitude": "-84.08",
                }
            },
            active_ids={str(terminal.id)},
        )

        self.assertEqual(snapshot["vehicles"], [])
        filter_runs.assert_called_once_with(
            route_id="route-a",
            feed_publisher__transit_system__code="mbta",
            run_lifecycle_state__in={"In Progress", "No Signal"},
        )
        redis.pipeline.assert_not_called()

    def test_sorts_vehicles_by_run_id(self):
        higher = self._run(run_id=UUID("00000000-0000-0000-0000-000000000002"))
        lower = self._run(run_id=UUID("00000000-0000-0000-0000-000000000001"))
        positions = {
            str(run.id): {"latitude": "9.93", "longitude": "-84.08"}
            for run in (higher, lower)
        }

        snapshot, _redis, _filter_runs, _pipeline = self._snapshot(
            [higher, lower],
            positions,
        )

        self.assertEqual(
            [vehicle["run_id"] for vehicle in snapshot["vehicles"]],
            [str(lower.id), str(higher.id)],
        )

    def test_serializes_all_optional_state_fields(self):
        full = self._run(run_id=UUID("00000000-0000-0000-0000-000000000001"))
        empty = self._run(
            run_id=UUID("00000000-0000-0000-0000-000000000002"),
            trip_id=None,
            direction_id=None,
        )
        positions = {
            str(full.id): {
                "latitude": "9.934739",
                "longitude": "-84.087502",
                "bearing": "180.5",
                "speed": "12.25",
                "odometer": "5000.75",
            },
            str(empty.id): {
                "latitude": "9.94",
                "longitude": "-84.09",
            },
        }
        scalars = {
            str(full.id): {
                "current_stop_sequence": "4",
                "stop_id": "stop-a",
                "current_status": "2",
                "congestion_level": "1",
                "occupancy_status": "3",
                "occupancy_percentage": "65",
                "timestamp": str(self.now_timestamp),
            }
        }

        snapshot, _redis, _filter_runs, _pipeline = self._snapshot(
            [full, empty],
            positions,
            scalars=scalars,
        )

        full_vehicle, empty_vehicle = snapshot["vehicles"]
        self.assertEqual(full_vehicle["latitude"], 9.934739)
        self.assertEqual(full_vehicle["longitude"], -84.087502)
        self.assertEqual(full_vehicle["bearing"], 180.5)
        self.assertEqual(full_vehicle["speed"], 12.25)
        self.assertEqual(full_vehicle["odometer"], 5000.75)
        self.assertEqual(full_vehicle["current_stop_sequence"], 4)
        self.assertEqual(full_vehicle["stop_id"], "stop-a")
        self.assertEqual(full_vehicle["current_status"], 2)
        self.assertEqual(full_vehicle["congestion_level"], 1)
        self.assertEqual(full_vehicle["occupancy_status"], 3)
        self.assertEqual(full_vehicle["occupancy_percentage"], 65)
        self.assertEqual(full_vehicle["timestamp"], self.now_timestamp)
        for field in (
            "trip_id",
            "direction_id",
            "bearing",
            "speed",
            "odometer",
            "current_stop_sequence",
            "stop_id",
            "current_status",
            "congestion_level",
            "occupancy_status",
            "occupancy_percentage",
            "timestamp",
        ):
            self.assertIsNone(empty_vehicle[field])

    def test_reads_all_vehicle_state_in_a_single_pipeline(self):
        first = self._run(run_id=UUID("00000000-0000-0000-0000-000000000001"))
        second = self._run(run_id=UUID("00000000-0000-0000-0000-000000000002"))
        runs = [first, second]
        positions = {
            str(run.id): {"latitude": "9.93", "longitude": "-84.08"} for run in runs
        }

        _snapshot, redis, _filter_runs, pipeline = self._snapshot(runs, positions)

        first_id, second_id = (str(run.id) for run in runs)
        self.assertEqual(
            pipeline.method_calls,
            [
                call.smismember("mbta:runs:active", [first_id, second_id]),
                call.hgetall(f"mbta:trip:{first_id}:position"),
                call.hgetall(f"mbta:trip:{second_id}:position"),
                call.mget(self._scalar_keys(first_id)),
                call.mget(self._scalar_keys(second_id)),
                call.execute(),
            ],
        )
        redis.pipeline.assert_called_once_with(transaction=False)
        pipeline.execute.assert_called_once_with()
        self.assertEqual(redis.method_calls, [call.pipeline(transaction=False)])

    def test_malformed_numeric_value_logs_warning_and_yields_none(self):
        run = self._run()

        with self.assertLogs(
            "updates.builders.route.vehicle_positions", level="WARNING"
        ) as logs:
            snapshot, _redis, _filter_runs, _pipeline = self._snapshot(
                [run],
                {
                    str(run.id): {
                        "latitude": "9.93",
                        "longitude": "-84.08",
                    }
                },
                scalars={str(run.id): {"timestamp": "not-a-number"}},
            )

        self.assertEqual(len(snapshot["vehicles"]), 1)
        self.assertIsNone(snapshot["vehicles"][0]["timestamp"])
        self.assertIn(f"mbta:trip:{run.id}:timestamp", logs.output[0])
        self.assertIn(str(run.id), logs.output[0])

    def test_pipeline_length_mismatch_raises(self):
        first = self._run(run_id=UUID("00000000-0000-0000-0000-000000000001"))
        second = self._run(run_id=UUID("00000000-0000-0000-0000-000000000002"))
        incomplete_pipeline_values: list[object] = [
            [1, 1],
            {"latitude": "9.93", "longitude": "-84.08"},
            [None] * 7,
            [None] * 7,
        ]

        with (
            patch(
                "updates.builders.route.vehicle_positions.VehiclePositionsByRouteSnapshot"
            ) as snapshot_model,
            self.assertRaises(ValueError),
        ):
            self._snapshot(
                [first, second],
                {},
                pipeline_values=incomplete_pipeline_values,
            )

        snapshot_model.assert_not_called()


class RouteVehiclePositionsProjectionTests(SimpleTestCase):
    def test_route_topic_round_trip(self):
        raw = "mbta.route.vehicle_positions.by_route.route-a"

        topic = TopicKey.parse(raw)

        self.assertEqual(topic.render(), raw)
        self.assertIsNone(topic.qualifier_selector)
        self.assertIsNone(topic.qualifier_value)

    def test_validator_rejects_empty_route_id(self):
        topic = TopicKey(
            transit_system="mbta",
            entity="route",
            info="vehicle_positions",
            primary_selector="by_route",
            primary_value="",
        )

        with self.assertRaises(InvalidTopicException):
            validate_vehicle_positions_topic(topic)

    def test_validator_accepts_populated_route_id(self):
        topic = TopicKey.parse("mbta.route.vehicle_positions.by_route.route-a")

        self.assertIsNone(validate_vehicle_positions_topic(topic))

    def test_registry_resolves_route_vehicle_positions_topic(self):
        projection = projection_for_topic(
            TopicKey.parse("mbta.route.vehicle_positions.by_route.route-a")
        )

        self.assertIsNotNone(projection)
        self.assertEqual(projection.name, "route_vehicle_positions")
        self.assertIs(projection.build, build_route_vehicle_positions)

    def test_registry_lookup_is_unambiguous(self):
        trip_occupancy = projection_for_topic(
            TopicKey.parse("mbta.trip.occupancy_status.by_run.run-a")
        )
        stop_occupancy = projection_for_topic(
            TopicKey.parse("mbta.stop.occupancy_status.by_stop.stop-a")
        )
        stop_time_updates = projection_for_topic(
            TopicKey.parse(
                "mbta.stop.stop_time_updates.by_stop.stop-a.by_direction.1"
            )
        )

        self.assertIsNotNone(trip_occupancy)
        self.assertEqual(trip_occupancy.name, "trip_occupancy_status")
        self.assertIsNotNone(stop_occupancy)
        self.assertEqual(stop_occupancy.name, "stop_occupancy_status")
        self.assertIsNotNone(stop_time_updates)
        self.assertEqual(stop_time_updates.name, "stop_stop_time_updates")

    @patch("updates.projections.route.vehicle_positions.Run.objects.filter")
    def test_lifecycle_resolver_returns_route_topic(self, filter_runs):
        filter_runs.return_value.values_list.return_value.first.return_value = (
            "route-a"
        )
        event = RunCompleted(
            transit_system="mbta",
            run_id=uuid4(),
            reason="Reached terminal.",
            occurred_at="2026-08-02T12:00:00Z",
        )

        topics = resolve_vehicle_positions_topics(event)

        self.assertEqual(
            [topic.render() for topic in topics],
            ["mbta.route.vehicle_positions.by_route.route-a"],
        )
        filter_runs.assert_called_once_with(
            id=event.run_id,
            feed_publisher__transit_system__code="mbta",
        )

    @patch("updates.projections.route.vehicle_positions.Run.objects.filter")
    def test_lifecycle_resolver_returns_empty_for_missing_run(self, filter_runs):
        filter_runs.return_value.values_list.return_value.first.return_value = None
        event = RunCompleted(
            transit_system="mbta",
            run_id=uuid4(),
            reason="Reached terminal.",
            occurred_at="2026-08-02T12:00:00Z",
        )

        self.assertEqual(resolve_vehicle_positions_topics(event), [])

    @patch("updates.projections.route.vehicle_positions.Run.objects.filter")
    def test_lifecycle_resolver_returns_empty_for_run_without_route_id(
        self,
        filter_runs,
    ):
        first = filter_runs.return_value.values_list.return_value.first
        first.side_effect = [None, ""]
        event = RunCompleted(
            transit_system="mbta",
            run_id=uuid4(),
            reason="Reached terminal.",
            occurred_at="2026-08-02T12:00:00Z",
        )

        self.assertEqual(resolve_vehicle_positions_topics(event), [])
        self.assertEqual(resolve_vehicle_positions_topics(event), [])

    def test_lifecycle_event_resolves_both_stop_time_and_vehicle_position(self):
        event = RunCompleted(
            transit_system="mbta",
            run_id=uuid4(),
            reason="Reached terminal.",
            occurred_at="2026-08-02T12:00:00Z",
        )

        projection_names = {
            projection.name for projection in projections_for_event(event)
        }

        self.assertIn("stop_stop_time_updates", projection_names)
        self.assertIn("route_vehicle_positions", projection_names)


class ActiveTopicRefreshTests(SimpleTestCase):
    @patch("updates.refresh.dispatch")
    @patch("updates.refresh.projection_for_topic")
    @patch("updates.refresh.has_subscribers", return_value=True)
    @patch("updates.refresh.active_subscription_topics")
    def test_vehicle_refresh_dispatches_only_route_vehicle_position_topics(
        self,
        active_topics,
        _has_subscribers,
        projection_for_topic_mock,
        dispatch,
    ):
        from updates.refresh import refresh_active_vehicle_position_topics

        stop_time = "mbta.stop.stop_time_updates.by_stop.A.by_direction.1"
        occupancy = "mbta.stop.occupancy_status.by_stop.A"
        vehicle_positions = "mbta.route.vehicle_positions.by_route.route-a"
        other_system = "other.route.vehicle_positions.by_route.route-b"
        active_topics.return_value = {
            stop_time,
            occupancy,
            vehicle_positions,
            other_system,
        }
        stop_time_projection = SimpleNamespace(name="stop_stop_time_updates")
        occupancy_projection = SimpleNamespace(name="stop_occupancy_status")
        vehicle_projection = SimpleNamespace(
            name="route_vehicle_positions",
            validate_topic=Mock(),
            build=Mock(return_value={"vehicles": []}),
        )
        projection_for_topic_mock.side_effect = lambda topic: {
            "stop_time_updates": stop_time_projection,
            "occupancy_status": occupancy_projection,
            "vehicle_positions": vehicle_projection,
        }[topic.info]

        count = refresh_active_vehicle_position_topics("mbta")

        self.assertEqual(count, 1)
        vehicle_projection.build.assert_called_once_with(
            TopicKey.parse(vehicle_positions)
        )
        dispatch.assert_called_once_with(
            TopicKey.parse(vehicle_positions),
            {"vehicles": []},
        )

    @patch("updates.refresh.dispatch")
    @patch("updates.refresh.projection_for_topic")
    @patch("updates.refresh.has_subscribers", return_value=True)
    @patch("updates.refresh.active_subscription_topics")
    def test_stop_time_refresh_ignores_route_vehicle_position_topics(
        self,
        active_topics,
        _has_subscribers,
        projection_for_topic_mock,
        dispatch,
    ):
        from updates.refresh import refresh_active_stop_time_update_topics

        stop_time = "mbta.stop.stop_time_updates.by_stop.A.by_direction.1"
        vehicle_positions = "mbta.route.vehicle_positions.by_route.route-a"
        active_topics.return_value = {stop_time, vehicle_positions}
        stop_time_projection = SimpleNamespace(
            name="stop_stop_time_updates",
            validate_topic=Mock(),
            build=Mock(return_value={"stop_time_updates": []}),
        )
        vehicle_projection = SimpleNamespace(
            name="route_vehicle_positions",
            validate_topic=Mock(),
            build=Mock(return_value={"vehicles": []}),
        )
        projection_for_topic_mock.side_effect = lambda topic: (
            stop_time_projection
            if topic.info == "stop_time_updates"
            else vehicle_projection
        )

        count = refresh_active_stop_time_update_topics("mbta")

        self.assertEqual(count, 1)
        vehicle_projection.build.assert_not_called()
        dispatch.assert_called_once_with(
            TopicKey.parse(stop_time),
            {"stop_time_updates": []},
        )

    @patch("updates.refresh.active_subscription_topics", return_value=set())
    def test_stop_time_refresh_log_message_is_unchanged(self, _active_topics):
        from updates.refresh import refresh_active_stop_time_update_topics

        with self.assertLogs("updates.refresh", level="INFO") as logs:
            count = refresh_active_stop_time_update_topics("mbta")

        self.assertEqual(count, 0)
        self.assertEqual(
            [record.getMessage() for record in logs.records],
            [
                "Refreshed 0 active stop-time-update topics for transit system mbta"
            ],
        )

    @patch("updates.refresh.dispatch")
    @patch("updates.refresh.projection_for_topic")
    @patch("updates.refresh.has_subscribers", return_value=False)
    @patch("updates.refresh.active_subscription_topics")
    def test_vehicle_refresh_skips_topic_without_subscribers(
        self,
        active_topics,
        _has_subscribers,
        projection_for_topic_mock,
        dispatch,
    ):
        from updates.refresh import refresh_active_vehicle_position_topics

        vehicle_positions = "mbta.route.vehicle_positions.by_route.route-a"
        active_topics.return_value = {vehicle_positions}
        projection = SimpleNamespace(
            name="route_vehicle_positions",
            validate_topic=Mock(),
            build=Mock(return_value={"vehicles": []}),
        )
        projection_for_topic_mock.return_value = projection

        count = refresh_active_vehicle_position_topics("mbta")

        self.assertEqual(count, 0)
        projection.build.assert_not_called()
        dispatch.assert_not_called()

    @patch("updates.refresh.dispatch")
    @patch("updates.refresh.projection_for_topic")
    @patch("updates.refresh.has_subscribers", return_value=True)
    @patch("updates.refresh.active_subscription_topics")
    def test_vehicle_refresh_isolates_a_failing_builder(
        self,
        active_topics,
        _has_subscribers,
        projection_for_topic_mock,
        dispatch,
    ):
        from updates.refresh import refresh_active_vehicle_position_topics

        broken = "mbta.route.vehicle_positions.by_route.route-a"
        healthy = "mbta.route.vehicle_positions.by_route.route-b"
        active_topics.return_value = {broken, healthy}
        projection = SimpleNamespace(
            name="route_vehicle_positions",
            validate_topic=Mock(),
            build=Mock(side_effect=[RuntimeError("broken builder"), {"ok": True}]),
        )
        projection_for_topic_mock.return_value = projection

        count = refresh_active_vehicle_position_topics("mbta")

        self.assertEqual(count, 1)
        dispatch.assert_called_once_with(
            TopicKey.parse(healthy),
            {"ok": True},
        )

    @patch("updates.refresh.dispatch")
    @patch("updates.refresh.projection_for_topic")
    @patch("updates.refresh.has_subscribers", return_value=True)
    @patch("updates.refresh.active_subscription_topics")
    def test_vehicle_refresh_applies_projection_validator(
        self,
        active_topics,
        _has_subscribers,
        projection_for_topic_mock,
        dispatch,
    ):
        from updates.refresh import refresh_active_vehicle_position_topics

        rejected = "mbta.route.vehicle_positions.by_route.route-a"
        healthy = "mbta.route.vehicle_positions.by_route.route-b"
        active_topics.return_value = {rejected, healthy}

        def validate_topic(topic):
            if topic.primary_value == "route-a":
                raise InvalidTopicException(topic.render(), "Rejected route.")

        projection = SimpleNamespace(
            name="route_vehicle_positions",
            validate_topic=Mock(side_effect=validate_topic),
            build=Mock(return_value={"vehicles": []}),
        )
        projection_for_topic_mock.return_value = projection

        count = refresh_active_vehicle_position_topics("mbta")

        self.assertEqual(count, 1)
        projection.build.assert_called_once_with(TopicKey.parse(healthy))
        dispatch.assert_called_once_with(
            TopicKey.parse(healthy),
            {"vehicles": []},
        )

    @patch("updates.refresh.dispatch")
    @patch("updates.refresh.projection_for_topic")
    @patch("updates.refresh.has_subscribers", return_value=True)
    @patch("updates.refresh.active_subscription_topics")
    def test_refresh_ignores_malformed_topic_in_active_set(
        self,
        active_topics,
        _has_subscribers,
        projection_for_topic_mock,
        dispatch,
    ):
        from updates.refresh import refresh_active_vehicle_position_topics

        malformed = "not-a-valid-topic"
        healthy = "mbta.route.vehicle_positions.by_route.route-a"
        active_topics.return_value = {malformed, healthy}
        projection = SimpleNamespace(
            name="route_vehicle_positions",
            validate_topic=Mock(),
            build=Mock(return_value={"vehicles": []}),
        )
        projection_for_topic_mock.return_value = projection

        with self.assertLogs("updates.refresh", level="WARNING") as logs:
            count = refresh_active_vehicle_position_topics("mbta")

        self.assertEqual(count, 1)
        self.assertEqual(
            logs.output,
            [
                "WARNING:updates.refresh:Ignoring invalid topic in active "
                "subscriptions: not-a-valid-topic"
            ],
        )
        dispatch.assert_called_once_with(
            TopicKey.parse(healthy),
            {"vehicles": []},
        )
