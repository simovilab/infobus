import json
import logging
from typing import Literal, TypedDict

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.conf import settings
from redis import Redis

from .exceptions import InvalidTopicException
from .planner import build_topic_snapshot
from .registry import Snapshot
from .subscriptions import add_subscription, remove_subscription
from .topics import TopicKey


r: Redis = Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_CELERY_DB
)
logger = logging.getLogger(__name__)


class RealtimeMessageEvent(TypedDict):
    """Describe a snapshot event received from the Channels layer."""

    type: Literal["realtime_message"]
    topic: str
    message: Snapshot


class UpdatesConsumer(WebsocketConsumer):
    """Provide topic-based real-time subscriptions over WebSocket."""

    subscriptions: set[TopicKey]

    def connect(self) -> None:
        """Accept the connection and initialize its subscriptions."""
        self.subscriptions = set()
        self.accept()
        self._send_json({"type": "connected"})

    def disconnect(self, close_code: int) -> None:
        """Remove every subscription owned by the closing connection."""
        logger.debug(
            "Disconnecting WebSocket channel %s with code %s",
            self.channel_name,
            close_code,
        )
        for topic in list(self.subscriptions):
            async_to_sync(self.channel_layer.group_discard)(
                topic.group_name(), self.channel_name
            )
            remove_subscription(r, topic.render(), self.channel_name)
        self.subscriptions.clear()

    def receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
    ) -> None:
        """Handle a text subscribe or unsubscribe command."""
        if bytes_data is not None:
            self._send_error("Binary WebSocket messages are not supported.")
            return
        if text_data is None:
            self._send_error("A text WebSocket message is required.")
            return

        try:
            message = json.loads(text_data)
            if not isinstance(message, dict):
                raise ValueError("The WebSocket message must be a JSON object.")
            topic = TopicKey.parse(message["topic"])
            action = message["action"]
            if action == "subscribe":
                self.subscribe(topic)
            elif action == "unsubscribe":
                self.unsubscribe(topic)
            else:
                raise ValueError(f"Unsupported action: {action}")
        except (InvalidTopicException, KeyError, TypeError, ValueError) as error:
            self._send_error(str(error))

    def subscribe(self, topic: TopicKey) -> None:
        """Join a topic and send its current snapshot when available."""
        group_name = topic.group_name()
        async_to_sync(self.channel_layer.group_add)(group_name, self.channel_name)
        try:
            add_subscription(r, topic.render(), self.channel_name)
        except Exception:
            async_to_sync(self.channel_layer.group_discard)(
                group_name, self.channel_name
            )
            raise

        self.subscriptions.add(topic)
        self._send_json({"type": "subscribed", "topic": topic.render()})

        snapshot = build_topic_snapshot(topic)
        if snapshot is not None:
            self._send_json({"topic": topic.render(), "message": snapshot})

    def unsubscribe(self, topic: TopicKey) -> None:
        """Leave a topic and remove its subscription metadata."""
        async_to_sync(self.channel_layer.group_discard)(
            topic.group_name(), self.channel_name
        )
        remove_subscription(r, topic.render(), self.channel_name)
        self.subscriptions.discard(topic)
        self._send_json({"type": "unsubscribed", "topic": topic.render()})

    def realtime_message(self, event: RealtimeMessageEvent) -> None:
        """Forward a Channels snapshot event to the WebSocket client."""
        self._send_json({"topic": event["topic"], "message": event["message"]})

    def _send_json(self, payload: object) -> None:
        """Serialize and send one JSON WebSocket message."""
        self.send(text_data=json.dumps(payload))

    def _send_error(self, message: str) -> None:
        """Send a protocol error without closing the connection."""
        logger.debug("WebSocket protocol error: %s", message)
        self._send_json({"type": "error", "message": message})
