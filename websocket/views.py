"""
WebSocket Demo Views
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from gtfs.models import TripUpdate


def trip_demo(request):
    """
    Render WebSocket trip demo page.
    Auto-detects hostname and available trips.
    """
    # Get available demo trips
    demo_trips = TripUpdate.objects.filter(
        trip_trip_id__startswith='DEMO_'
    ).values_list('trip_trip_id', flat=True).distinct()[:10]
    
    context = {
        'demo_trips': list(demo_trips),
        'default_trip': demo_trips[0] if demo_trips else 'DEMO_SJ_HEREDIA_001',
    }
    return render(request, 'websocket/trip_demo.html', context)


@require_http_methods(["GET"])
def demo_status(request):
    """
    Check if demo data exists.
    """
    demo_trips = TripUpdate.objects.filter(
        trip_trip_id__startswith='DEMO_'
    ).count()
    
    return JsonResponse({
        'demo_ready': demo_trips > 0,
        'demo_trips_count': demo_trips,
        'instructions': (
            'Run: docker-compose exec web uv run python manage.py demo_websocket_data'
            if demo_trips == 0 else 'Demo data ready'
        )
    })
