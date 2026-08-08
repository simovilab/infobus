from .stop.stop_time_updates import stop_time_updates as stop_stop_time_updates
from .trip.stop_time_updates import stop_time_updates as trip_stop_time_updates


def message_builder(entity, info, namespace, instance, attribute):
    """Route a source instance to the stop- or trip-level stop-time-update payload builder selected by entity type."""
    if entity == "stop":
        message = stop_stop_time_updates(instance)
    elif entity == "trip":
        message = trip_stop_time_updates(instance)
    else:
        message = None
    return message
