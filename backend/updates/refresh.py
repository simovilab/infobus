import logging

from django.conf import settings
from redis import Redis

from .dispatcher import dispatch
from .exceptions import InvalidTopicException
from .registry import projection_for_topic
from .subscriptions import active_subscription_topics, has_subscribers
from .topics import TopicKey


logger = logging.getLogger(__name__)
r = Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_CELERY_DB,
    decode_responses=True,
)

def _refresh_active_topics(
    transit_system: str,
    projection_names: frozenset[str],
    log_label: str,
) -> int:
    """Rebuild and dispatch active topics for a projection after a successful poll."""
    topics: set[TopicKey] = set()
    for raw_topic in active_subscription_topics(r):
        try:
            topic = TopicKey.parse(raw_topic)
        except InvalidTopicException:
            logger.warning(
                "Ignoring invalid topic in active subscriptions: %s",
                raw_topic,
            )
            continue
        if topic.transit_system != transit_system:
            continue

        projection = projection_for_topic(topic)
        if projection is None or projection.name not in projection_names:
            continue
        if not has_subscribers(r, raw_topic):
            continue
        topics.add(topic)

    dispatched = 0
    for topic in sorted(topics, key=TopicKey.render):
        try:
            projection = projection_for_topic(topic)
            if projection is None or projection.name not in projection_names:
                continue
            if not has_subscribers(r, topic.render()):
                continue
            if projection.validate_topic is not None:
                projection.validate_topic(topic)
            payload = projection.build(topic)
            if payload is None:
                continue
            dispatch(topic, payload)
            dispatched += 1
        except Exception:
            logger.exception("Failed to refresh active topic %s", topic.render())
    logger.info(
        "Refreshed %s active %s topics for transit system %s",
        dispatched,
        log_label,
        transit_system,
    )
    return dispatched


def refresh_active_stop_time_update_topics(transit_system: str) -> int:
    """Rebuild and dispatch active stop-time topics after a successful poll."""
    return _refresh_active_topics(
        transit_system,
        frozenset({"stop_stop_time_updates"}),
        "stop-time-update",
    )


def refresh_active_vehicle_position_topics(transit_system: str) -> int:
    """Rebuild and dispatch active route vehicle-position topics after a poll."""
    return _refresh_active_topics(
        transit_system,
        frozenset(
            {"route_vehicle_positions", "route_vehicle_positions_by_direction"}
        ),
        "route-vehicle-position",
    )
