from django.shortcuts import render

from screens.models import StopScreen

# Create your views here.


def stop_screen(request, stop_slug):
    screen = StopScreen.objects.get(stop_slug=stop_slug)
    stop = screen.stop
    context = {"screen": screen, "stop": stop}
    return render(request, "stop_screen.html", context)
