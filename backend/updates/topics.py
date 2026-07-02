class UpdatesTopics:
    """
    This class defines the structure and naming conventions for real-time topics in the Infobús system.
    Each topic follows a specific format to ensure consistency and ease of use across different types of data.

    Example topic anatomy:
    <entity>.<info>[.<namespace>].<instance>.<attribute>

    - Entity: the GTFS entity (trip, stop, route, alert, etc)
    - Info: the type of information or aspect of the entity (stop_time_updates, vehicle_positions, alerts, etc)
    - Namespace: an optional further categorization to create a new namespace for related topics (e.g., alert types, route types, etc)
    - Instance: the specific identifier for the entity instance (run_id, stop_id, route_id, etc)
    - Attribute: the specific attribute of the entity instance (e.g., arrival_time, departure_time, etc)
    """

    _ALLOWED_THREE_PART_TOPICS = {
        ("trip", "stop_time_updates"),
        ("trip", "vehicle_stop_status"),
        ("trip", "congestion_level"),
        ("trip", "occupancy_status"),
        ("trip", "alerts"),
        ("stop", "stop_time_updates"),
        ("stop", "vehicle_positions"),
        ("stop", "alerts"),
        ("route", "vehicle_positions"),
        ("route", "alerts"),
        ("agency", "alerts"),
    }

    @staticmethod
    def validate_topic(topic):
        parts = topic.split(".")

        if len(parts) == 3:
            entity, info, instance = parts
            if not instance:
                return False
            return (entity, info) in UpdatesTopics._ALLOWED_THREE_PART_TOPICS

        if len(parts) == 4:
            entity, info, third, fourth = parts
            if not third or not fourth:
                return False

            # route.alerts.type.<route_type>
            if entity == "route" and info == "alerts" and third == "type":
                return True

            # route.alerts.<route_id>.<direction_id>
            if entity == "route" and info == "alerts":
                return True

        return False

    @staticmethod
    def topic_builder(message):
        entity = message.get("entity")
        info = message.get("info")
        instance = message.get("instance")

        if not entity or not info or not instance:
            raise ValueError("subscribe messages require entity, info, and instance")

        topic_parts = [entity, info]

        namespace = message.get("namespace")
        if namespace:
            topic_parts.append(namespace)

        topic_parts.append(instance)

        attribute = message.get("attribute")
        if attribute:
            topic_parts.append(attribute)

        topic = ".".join(topic_parts)

        if not UpdatesTopics.validate_topic(topic):
            raise ValueError(f"invalid topic format: {topic}")

        return topic
