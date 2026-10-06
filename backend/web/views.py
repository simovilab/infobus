"""Backend-for-frontend (BFF) views that serve page-oriented data to Infobús Web."""

from django.db.models import QuerySet
from rest_framework import viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from feed.models import Feed, Route, Stop, TransitSystem

from .serializers import WebRouteSerializer, WebStopSerializer


class TransitSystemScopedMixin:
    """Resolve the transit system that a request refers to.

    Temporary rule, pending a decision on how URLs identify the transit system:
    use ``?system=<code>`` when given; otherwise use the only active system;
    otherwise reject the request with HTTP 400.
    """

    request: Request

    def get_transit_system(self) -> TransitSystem:
        """Return the active transit system selected by the request."""
        active = TransitSystem.objects.filter(is_active=True).order_by("code")
        code = self.request.query_params.get("system")
        if code:
            try:
                return active.get(code=code)
            except TransitSystem.DoesNotExist:
                raise NotFound(
                    f"No active transit system with code '{code}'."
                ) from None
        systems = list(active)
        if len(systems) == 1:
            return systems[0]
        raise ValidationError(
            {
                "system": "Specify ?system=<code>. Valid codes: "
                + ", ".join(system.code for system in systems)
            }
        )


class HomeViewSet(TransitSystemScopedMixin, viewsets.ViewSet):
    """Summarize the selected transit system and its current GTFS Schedule feeds for the Home page."""

    def list(self, request: Request) -> Response:
        """Return the selected transit system with its current Schedule feeds."""
        system = self.get_transit_system()
        feeds = Feed.objects.filter(
            is_current=True,
            feed_publisher__transit_system=system,
        ).order_by("feed_publisher__code")
        return Response(
            {
                "transit_system": {"code": system.code, "name": system.name},
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


class RoutesViewSet(TransitSystemScopedMixin, viewsets.ReadOnlyModelViewSet):
    """List and retrieve routes from the selected transit system's current Schedule feeds.

    Known limitation: if one transit system had several publishers whose current
    feeds share a ``route_id``, retrieval would fail; today each system has one
    publisher.
    """

    serializer_class = WebRouteSerializer
    lookup_field = "route_id"
    # GTFS identifiers may contain dots; only "/" is excluded.
    lookup_value_regex = "[^/]+"

    def get_queryset(self) -> QuerySet[Route]:
        """Return routes in the selected system's current feeds, in a stable order."""
        return Route.objects.filter(
            feed__is_current=True,
            feed__feed_publisher__transit_system=self.get_transit_system(),
        ).order_by("pk")


class StopsViewSet(TransitSystemScopedMixin, viewsets.ReadOnlyModelViewSet):
    """List and retrieve stops from the selected transit system's current Schedule feeds.

    Known limitation: if one transit system had several publishers whose current
    feeds share a ``stop_id``, retrieval would fail; today each system has one
    publisher.
    """

    serializer_class = WebStopSerializer
    lookup_field = "stop_id"
    # GTFS identifiers may contain dots; only "/" is excluded.
    lookup_value_regex = "[^/]+"

    def get_queryset(self) -> QuerySet[Stop]:
        """Return stops in the selected system's current feeds, in a stable order."""
        return Stop.objects.filter(
            feed__is_current=True,
            feed__feed_publisher__transit_system=self.get_transit_system(),
        ).order_by("pk")
