from django.shortcuts import render


from feed.models import Agency
from screens.models import StopScreen

# Create your views here.


def stop_screen(request, stop_slug):
    screen = StopScreen.objects.get(stop_slug=stop_slug)
    stop = screen.stop
    agency = Agency.objects.filter(feed=stop.feed).first()
    context = {
        "screen": screen,
        "stop": stop,
        "agency_timezone": agency.agency_timezone if agency else None,
    }
    return render(request, "stop_screen.html", context)
