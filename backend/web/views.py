"""Backend-for-frontend (BFF) views that serve page-oriented data to Infobús Web."""

from rest_framework import viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from feed.models import Feed, TransitSystem


class HomeViewSet(viewsets.ViewSet):
    """Summarize active transit systems and their current GTFS Schedule feeds for the Home page."""

    def list(self, request: Request) -> Response:
        """Return each active transit system with its current Schedule feeds."""
        systems = []
        for system in TransitSystem.objects.filter(is_active=True).order_by("code"):
            feeds = Feed.objects.filter(
                is_current=True,
                feed_publisher__transit_system=system,
            ).order_by("feed_publisher__code")
            systems.append(
                {
                    "code": system.code,
                    "name": system.name,
                    "current_feeds": [
                        {
                            "feed_id": feed.feed_id,
                            "version": feed.version,
                            "start_date": feed.start_date,
                            "end_date": feed.end_date,
                        }
                        for feed in feeds
                    ],
                }
            )
        return Response({"transit_systems": systems})
