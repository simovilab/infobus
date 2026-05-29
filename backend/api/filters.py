from django_filters import rest_framework as filters

from feed.models import Feed, FeedPublisher


class FeedPublisherFilter(filters.FilterSet):
    transit_system = filters.CharFilter(field_name="transit_system__code")

    class Meta:
        model = FeedPublisher
        fields = ["code", "name"]


class FeedFilter(filters.FilterSet):
    transit_system = filters.CharFilter(
        field_name="feed_publisher__transit_system__code"
    )

    class Meta:
        model = Feed
        fields = ["feed_id", "feed_publisher", "is_current"]
