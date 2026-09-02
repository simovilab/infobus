import json
import logging
import os
import socket
import time

import django
from django.conf import settings
from pydantic import ValidationError
from redis import Redis
from redis.exceptions import ResponseError

STREAM_NAME = "events"
GROUP_NAME = "updates"
DEAD_LETTER_STREAM = "events:dead-letter"
CLAIM_IDLE_MS = 60_000

logger = logging.getLogger("updates.client")


def _ensure_consumer_group(redis: Redis) -> None:
    """Create the updates consumer group when it does not exist."""
    try:
        redis.xgroup_create(STREAM_NAME, GROUP_NAME, id="$", mkstream=True)
    except ResponseError as error:
        if "BUSYGROUP" not in str(error):
            raise


def _process_entries(
    redis: Redis,
    entries: list[tuple[str, dict[str, str]]],
    consumer_name: str,
) -> None:
    """Validate, process, and acknowledge a batch of stream entries."""
    from .events import parse_event
    from .planner import process_event

    for event_id, fields in entries:
        try:
            event = parse_event(fields)
        except (ValidationError, ValueError) as error:
            logger.exception("Invalid update event %s", event_id)
            redis.xadd(
                DEAD_LETTER_STREAM,
                {
                    "source_event_id": event_id,
                    "consumer": consumer_name,
                    "error": str(error),
                    "payload": json.dumps(fields),
                },
                maxlen=settings.REDIS_DEAD_LETTER_STREAM_MAXLEN,
                approximate=True,
            )
            redis.xack(STREAM_NAME, GROUP_NAME, event_id)
            continue

        try:
            process_event(event)
        except Exception:
            logger.exception("Failed to process update event %s", event_id)
            continue

        redis.xack(STREAM_NAME, GROUP_NAME, event_id)


def _claim_stale_entries(redis: Redis, consumer_name: str) -> None:
    """Reclaim and process entries left pending by inactive consumers."""
    claimed = redis.xautoclaim(
        STREAM_NAME,
        GROUP_NAME,
        consumer_name,
        min_idle_time=CLAIM_IDLE_MS,
        start_id="0-0",
        count=100,
    )
    if len(claimed) >= 2 and claimed[1]:
        _process_entries(redis, claimed[1], consumer_name)


def consume_events() -> None:
    """Continuously consume and process events from the Redis stream."""
    redis = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_CELERY_DB,
        decode_responses=True,
    )
    consumer_name = f"{socket.gethostname()}-{os.getpid()}"
    _ensure_consumer_group(redis)
    last_claim_at = 0.0

    logger.info(
        "Waiting for events on Redis stream name '%s' as consumer name '%s'",
        STREAM_NAME,
        consumer_name,
    )

    while True:
        if time.monotonic() - last_claim_at >= CLAIM_IDLE_MS / 1000:
            _claim_stale_entries(redis, consumer_name)
            last_claim_at = time.monotonic()

        streams = redis.xreadgroup(
            GROUP_NAME,
            consumer_name,
            {STREAM_NAME: ">"},
            count=100,
            block=5_000,
        )
        for _, events in streams:
            _process_entries(redis, events, consumer_name)


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "infobus.settings")
    django.setup()
    consume_events()
