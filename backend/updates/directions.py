from .exceptions import InvalidTopicException
from .schemas import DirectionID
from .topics import TopicKey


VALID_DIRECTION_IDS: dict[str, DirectionID] = {"0": 0, "1": 1}


def direction_id_from_topic(topic: TopicKey) -> DirectionID:
    """Return a canonical GTFS direction ID or reject the concrete topic."""
    value = topic.qualifier_value
    if value not in VALID_DIRECTION_IDS:
        raise InvalidTopicException(
            topic.render(),
            "direction_id must be the canonical GTFS value 0 or 1.",
        )
    return VALID_DIRECTION_IDS[value]
