from dataclasses import dataclass
from .exceptions import InvalidTopicException


@dataclass(frozen=True)
class TopicKey:
    entity: str
    info: str
    primary_selector: str
    primary_value: str
    qualifier_selector: str | None = None
    qualifier_value: str | None = None

    @classmethod
    def parse(cls, raw: str) -> "TopicKey":
        parts = raw.split(".")

        if len(parts) not in (4, 6):
            raise InvalidTopicException("A topic must have 4 or 6 segments.")

        entity, info, selector, value = parts[:4]

        if len(parts) == 6:
            qualifier_selector, qualifier_value = parts[4:]
        else:
            qualifier_selector = qualifier_value = None

        return cls(
            entity=entity,
            info=info,
            primary_selector=selector,
            primary_value=value,
            qualifier_selector=qualifier_selector,
            qualifier_value=qualifier_value,
        )


@dataclass(frozen=True)
class TopicPattern:
    entity: str
    info: str
    primary_selector: str
    qualifier_selector: str | None = None

    def matches(self, topic: TopicKey) -> bool:
        return (
            self.entity == topic.entity
            and self.info == topic.info
            and self.primary_selector == topic.primary_selector
            and self.qualifier_selector == topic.qualifier_selector
        )


def UpdatesTopics():
    pass
