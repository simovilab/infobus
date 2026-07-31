import os

import django
from django.conf import settings
from redis import Redis

STREAM_NAME = "events"


def consume_events() -> None:
    redis = Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_CELERY_DB,
        decode_responses=True,
    )
    last_event_id = "$"

    print(f"Waiting for events on Redis stream '{STREAM_NAME}'...", flush=True)

    while True:
        streams = redis.xread({STREAM_NAME: last_event_id}, block=0)
        for _, events in streams:
            for event_id, message in events:
                last_event_id = event_id
                print(f"{event_id}: {message}", flush=True)


if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "infobus.settings")
    django.setup()
    consume_events()
