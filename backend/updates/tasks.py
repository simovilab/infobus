from celery import shared_task
from redis import Redis
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from feed.models import Stop
from feed.services.queries import get_next_trips
from gtfs.utils import channel_safe_payload

r = Redis(
    host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=settings.REDIS_CELERY_DB
)


@shared_task
def realtime_updates():
    """Retrieves new real-time information and updates the connected screens for a given stop or station."""

    active_subscriptions = r.smembers("active_subscriptions")
    active_subscriptions = [key.decode("utf-8") for key in active_subscriptions]

    stop_time_updates = {
        key for key in active_subscriptions if key.startswith("stop.stop_time_updates.")
    }

    for key in stop_time_updates:
        transit_system = 1
        stop_id = key.split(".")[-1]
        stop = Stop.objects.filter(stop_id=stop_id).first()
        if stop is None:
            continue
        stop_time_update_message = get_next_trips(transit_system, stop.stop_id)

        if stop_time_update_message is not None:
            safe_message = channel_safe_payload(stop_time_update_message)
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                key,
                {
                    "type": "realtime_message",
                    "message": safe_message,
                },
            )

    return "Updated screens successfully"
