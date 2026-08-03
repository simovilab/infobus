from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase

from runs.events.types import OccupancyStatusChanged
from runs.events.types import RunCompleted
from updates.consumers import UpdatesConsumer
from updates.events import parse_event
from updates.exceptions import InvalidTopicException
from updates.planner import process_event
from updates.projections.stop.occupancy_status import (
    resolve_stop_occupancy_topics,
)
from updates.projections.trip.occupancy_status import (
    resolve_trip_occupancy_topics,
)
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
