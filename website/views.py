from django.shortcuts import render

# Create your views here.


def index(request):
    return render(request, "index.html")


def about(request):
    return render(request, "about.html")


def profile(request):
    return render(request, "profile.html")


def realtime_map(request):
    """
    Production-ready real-time vehicle tracking with Leaflet map.
    
    Provider-agnostic view that works with any GTFS-RT data source.
    Routes are loaded dynamically from API endpoint.
    
    Configuration via settings.py:
        REALTIME_MAP_CENTER: [lat, lon] - Default map center
        REALTIME_MAP_ZOOM: int - Default zoom level
        REALTIME_MAP_TITLE: str - Page title
    """
    from django.conf import settings
    
    context = {
        'map_center': getattr(settings, 'REALTIME_MAP_CENTER', [0, 0]),
        'map_zoom': getattr(settings, 'REALTIME_MAP_ZOOM', 12),
        'page_title': getattr(settings, 'REALTIME_MAP_TITLE', 'Infobús - Real-time Tracking'),
        'provider_name': getattr(settings, 'REALTIME_MAP_PROVIDER', 'Transit Agency'),
    }
    
    return render(request, "website/realtime_map.html", context)
