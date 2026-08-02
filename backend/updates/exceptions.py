class InvalidTopicException(ValueError):
    """Report a public topic that cannot be parsed or validated."""

    def __init__(self, topic: object, reason: str) -> None:
        """Initialize the error with the rejected value and reason."""
        self.topic = topic
        self.reason = reason
        super().__init__(f"Invalid topic {topic!r}: {reason}")
