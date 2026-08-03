from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .registry import Snapshot
from .topics import TopicKey


def dispatch(topic: TopicKey, payload: Snapshot) -> None:
    """Send a topic snapshot to its Django Channels group."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        topic.group_name(),
        {
            "type": "realtime_message",
            "topic": topic.render(),
            "message": payload,
        },
    )
