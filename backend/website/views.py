from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from feed.models import Stop

# Create your views here.


def index(request: HttpRequest) -> HttpResponse:
    """Render the public landing-page template."""
    return render(request, "index.html")


def about(request: HttpRequest) -> HttpResponse:
    """Render the project information template."""
    return render(request, "about.html")


def profile(request: HttpRequest) -> HttpResponse:
    """Render the user profile template."""
    return render(request, "profile.html")


def updates(request: HttpRequest) -> HttpResponse:
    """Render the update viewer with distinct current MBTA stops."""
    stops = (
        Stop.objects.filter(
            feed__is_current=True,
            feed__feed_publisher__transit_system__code="mbta",
        )
        .exclude(stop_id="")
        .order_by("stop_name", "stop_id")
        .values("stop_id", "stop_name")
        .distinct()
    )
    return render(
        request,
        "updates.html",
        {
            "stops": stops,
            "transit_system": "mbta",
        },
    )
