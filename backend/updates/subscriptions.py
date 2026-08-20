from redis import Redis


ACTIVE_SUBSCRIPTIONS_KEY = "active_subscriptions"


def _subscribers_key(topic: str) -> str:
    """Return the Redis key containing a topic's subscribed channels."""
    return f"subscriptions:{topic}"


def active_subscription_topics(redis: Redis) -> set[str]:
    """Return the public topics currently marked active."""
    return {
        value.decode("utf-8") if isinstance(value, bytes) else str(value)
        for value in redis.smembers(ACTIVE_SUBSCRIPTIONS_KEY)
    }


def has_subscribers(redis: Redis, topic: str) -> bool:
    """Return whether a topic still has at least one registered channel."""
    return bool(redis.scard(_subscribers_key(topic)))


def add_subscription(redis: Redis, topic: str, channel_name: str) -> None:
    """Atomically register a channel and mark its topic active."""
    with redis.pipeline(transaction=True) as pipe:
        pipe.sadd(_subscribers_key(topic), channel_name)
        pipe.sadd(ACTIVE_SUBSCRIPTIONS_KEY, topic)
        pipe.execute()


def remove_subscription(redis: Redis, topic: str, channel_name: str) -> None:
    """Remove a channel and clear topic metadata when it becomes inactive."""
    redis.eval(
        """
		redis.call('SREM', KEYS[1], ARGV[1])
		if redis.call('SCARD', KEYS[1]) == 0 then
			redis.call('DEL', KEYS[1])
			redis.call('SREM', KEYS[2], ARGV[2])
		end
		return 1
		""",
        2,
        _subscribers_key(topic),
        ACTIVE_SUBSCRIPTIONS_KEY,
        channel_name,
        topic,
    )
