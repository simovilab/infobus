from dataclasses import dataclass
from hashlib import sha256
from typing import Self

from .exceptions import InvalidTopicException


@dataclass(frozen=True)
class TopicKey:
    """Represent a public update topic as transit, entity, information, selector, and optional qualifier segments."""
    transit_system: str
    entity: str
    info: str
    primary_selector: str
    primary_value: str
    qualifier_selector: str | None = None
    qualifier_value: str | None = None

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Parse and validate a public topic string."""
        if not isinstance(raw, str):
            raise InvalidTopicException(raw, "A topic must be a string.")

        parts = raw.split(".")

        if len(parts) not in (5, 7):
            raise InvalidTopicException(raw, "A topic must have 5 or 7 segments.")

        transit_system, entity, info, selector, value = parts[:5]

        if len(parts) == 7:
            qualifier_selector, qualifier_value = parts[5:]
        else:
            qualifier_selector = qualifier_value = None

        if not all(parts):
            raise InvalidTopicException(raw, "Topic segments cannot be empty.")

        return cls(
            transit_system=transit_system,
            entity=entity,
            info=info,
            primary_selector=selector,
            primary_value=value,
            qualifier_selector=qualifier_selector,
            qualifier_value=qualifier_value,
        )

    def render(self) -> str:
        """Render the topic in its public dot-separated form."""
        parts = [
            self.transit_system,
            self.entity,
            self.info,
            self.primary_selector,
            self.primary_value,
        ]
        if self.qualifier_selector is not None and self.qualifier_value is not None:
            parts.extend([self.qualifier_selector, self.qualifier_value])
        return ".".join(parts)

    def __str__(self) -> str:
        """Return the public topic string."""
        return self.render()

    def group_name(self) -> str:
        """Return a deterministic Channels-safe group name."""
        digest = sha256(self.render().encode("utf-8")).hexdigest()
        return f"updates.{digest}"


@dataclass(frozen=True)
class TopicPattern:
    """Represent the entity, information, and selector constraints used to match concrete update topics."""
    entity: str
    info: str
    primary_selector: str
    qualifier_selector: str | None = None

    def matches(self, topic: TopicKey) -> bool:
        """Return whether a concrete topic matches this pattern."""
        return (
            self.entity == topic.entity
            and self.info == topic.info
            and self.primary_selector == topic.primary_selector
            and self.qualifier_selector == topic.qualifier_selector
        )
