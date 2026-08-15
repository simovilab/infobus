from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase

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
            [str(run_b_id), str(run_a_id)],
        )
        self.assertEqual(
            [update["stop_sequence"] for update in snapshot["stop_time_updates"]],
            [9, 8],
        )
        self.assertEqual(
            snapshot["stop_time_updates"][0]["schedule_relationship"],
            "SCHEDULED",
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
