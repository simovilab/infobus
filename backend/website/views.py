from django.shortcuts import render
from feed.models import Stop

# Create your views here.


def index(request):
    return render(request, "index.html")


def about(request):
    return render(request, "about.html")


def profile(request):
    return render(request, "profile.html")


def updates(request):
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
