"""
WebSocket Demo Views
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from gtfs.models import TripUpdate, Route, VehiclePosition


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


def route_demo(request):
    """
    Render WebSocket route demo page.
    Auto-detects hostname and available routes with active vehicles.
    """
    # Get routes that have active vehicles (demo or real)
    active_routes = VehiclePosition.objects.values_list(
        'vehicle_trip_route_id', flat=True
    ).distinct().order_by('vehicle_trip_route_id')[:20]
    
    # Get route details from GTFS Schedule
    routes = Route.objects.filter(route_id__in=active_routes).values(
        'route_id', 'route_short_name', 'route_long_name'
    )
    
    context = {
        'routes': list(routes),
        'default_route': routes[0]['route_id'] if routes else 'DEMO_ROUTE_001',
    }
    return render(request, 'websocket/route_demo.html', context)


@require_http_methods(["GET"])
def demo_status(request):
    """
    Check if demo data exists.
    """
    demo_trips = TripUpdate.objects.filter(
        trip_trip_id__startswith='DEMO_'
    ).count()
    
    demo_routes = Route.objects.filter(
        route_id__startswith='DEMO_'
    ).count()
    
    return JsonResponse({
        'demo_ready': demo_trips > 0 or demo_routes > 0,
        'demo_trips_count': demo_trips,
        'demo_routes_count': demo_routes,
        'instructions': (
            'Run: docker-compose exec web uv run python manage.py demo_websocket_data && '
            'docker-compose exec web uv run python manage.py demo_route_data'
            if demo_trips == 0 else 'Demo data ready'
        )
    })
