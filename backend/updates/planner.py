from .dispatcher import dispatch
from .events import UpdateEvent
from .registry import Snapshot, projections_for_event, projection_for_topic
from .topics import TopicKey


def process_event(event: UpdateEvent) -> None:
    """Rebuild and dispatch every projection affected by an event."""
    for projection in projections_for_event(event):
        for topic in set(projection.resolve_topics(event)):
            payload = projection.build(topic)
            if payload is not None:
                dispatch(topic, payload)


def build_topic_snapshot(topic: TopicKey) -> Snapshot | None:
    """Build the current snapshot for a registered topic."""
    projection = projection_for_topic(topic)
    if projection is None:
        return None
    return projection.build(topic)
