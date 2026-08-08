from django.shortcuts import render
from feed.models import Stop

# Create your views here.


def index(request):
    """Render the public landing-page template."""
    return render(request, "index.html")


def about(request):
    """Render the project information template."""
    return render(request, "about.html")


def profile(request):
    """Render the user profile template."""
    return render(request, "profile.html")


def updates(request):
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
