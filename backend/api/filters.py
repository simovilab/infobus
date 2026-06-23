from django_filters import rest_framework as filters

from feed.models import Feed, FeedPublisher


class FeedPublisherFilter(filters.FilterSet):
    transit_system = filters.CharFilter(field_name="transit_system__code")

    class Meta:
        model = FeedPublisher
        fields = ["code", "name"]


class FeedFilter(filters.FilterSet):
    # Lookup canónico via publisher: Feed.transit_system queda NULL en la
    # ingesta actual (ver engine/tasks.py:173). La relación operativa con
    # TransitSystem es Feed -> FeedPublisher -> TransitSystem.
    transit_system = filters.CharFilter(
        field_name="feed_publisher__transit_system__code"
    )

    class Meta:
        model = Feed
        fields = ["feed_id", "feed_publisher", "is_current"]
