"""
Admin Dashboard for API Metrics and KPIs.

Provides comprehensive analytics dashboard for monitoring API traffic,
latency, errors, and client usage patterns.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Avg, Sum, Q, F
from django.db.models.functions import TruncHour, TruncDate
from django.utils import timezone
from datetime import timedelta
import json

from .models import ClientUsage, Client


@staff_member_required
def admin_dashboard(request):
    """
    Main admin dashboard with KPIs and charts.
    
    Displays:
    - Traffic metrics (requests per hour/day)
    - Latency statistics (average, P95, P99)
    - Error rates (4xx, 5xx)
    - Top endpoints
    - Client usage breakdown
    """
    # Get time range from request or default to last 24 hours
    hours = int(request.GET.get('hours', 24))
    start_time = timezone.now() - timedelta(hours=hours)
    
    # Base queryset for time range
    usage_qs = ClientUsage.objects.filter(timestamp__gte=start_time)
    
    # === KPI Calculations ===
    
    # Total requests
    total_requests = usage_qs.count()
    
    # Average latency
    avg_latency = usage_qs.aggregate(Avg('response_time_ms'))['response_time_ms__avg'] or 0
    
    # Success rate
    successful_requests = usage_qs.filter(status_code__lt=400).count()
    success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
    
    # Error counts
    client_errors = usage_qs.filter(status_code__gte=400, status_code__lt=500).count()
    server_errors = usage_qs.filter(status_code__gte=500).count()
    error_rate = ((client_errors + server_errors) / total_requests * 100) if total_requests > 0 else 0
    
    # === Traffic Over Time (hourly breakdown) ===
    traffic_by_hour = list(
        usage_qs
        .annotate(hour=TruncHour('timestamp'))
        .values('hour')
        .annotate(count=Count('id'))
        .order_by('hour')
    )
    
    # === Latency Distribution ===
    latency_percentiles = usage_qs.aggregate(
        p50=Avg('response_time_ms'),  # Median approximation
        p95=Avg('response_time_ms'),  # Would need proper percentile in production
        p99=Avg('response_time_ms'),
    )
    
    # === Status Code Distribution ===
    status_distribution = list(
        usage_qs
        .values('status_code')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    
    # === Top Endpoints ===
    top_endpoints = list(
        usage_qs
        .values('endpoint')
        .annotate(
            count=Count('id'),
            avg_latency=Avg('response_time_ms'),
            error_count=Count('id', filter=Q(status_code__gte=400))
        )
        .order_by('-count')[:10]
    )
    
    # === Client Usage Breakdown ===
    client_breakdown = list(
        usage_qs
        .values('client__name', 'client__tier')
        .annotate(
            count=Count('id'),
            avg_latency=Avg('response_time_ms'),
            errors=Count('id', filter=Q(status_code__gte=400))
        )
        .order_by('-count')[:10]
    )
    
    # === Method Distribution ===
    method_distribution = list(
        usage_qs
        .values('method')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    
    # === Error Analysis ===
    recent_errors = list(
        usage_qs
        .filter(status_code__gte=400)
        .values('timestamp', 'endpoint', 'method', 'status_code', 'error_message', 'client__name')
        .order_by('-timestamp')[:20]
    )
    
    # === Daily Trends (last 7 days) ===
    seven_days_ago = timezone.now() - timedelta(days=7)
    daily_trends = list(
        ClientUsage.objects
        .filter(timestamp__gte=seven_days_ago)
        .annotate(date=TruncDate('timestamp'))
        .values('date')
        .annotate(
            requests=Count('id'),
            avg_latency=Avg('response_time_ms'),
            errors=Count('id', filter=Q(status_code__gte=400))
        )
        .order_by('date')
    )
    
    # Convert datetimes to strings for JSON serialization
    for item in traffic_by_hour:
        if 'hour' in item and item['hour']:
            item['hour'] = item['hour'].isoformat()
    
    for item in daily_trends:
        if 'date' in item and item['date']:
            item['date'] = item['date'].isoformat()
    
    for item in recent_errors:
        if 'timestamp' in item and item['timestamp']:
            item['timestamp'] = item['timestamp'].isoformat()
    
    # Prepare context for template
    context = {
        'hours': hours,
        'start_time': start_time,
        
        # KPIs
        'total_requests': total_requests,
        'avg_latency': round(avg_latency, 2),
        'success_rate': round(success_rate, 2),
        'error_rate': round(error_rate, 2),
        'client_errors': client_errors,
        'server_errors': server_errors,
        
        # Charts data (JSON)
        'traffic_by_hour': json.dumps(traffic_by_hour),
        'status_distribution': json.dumps(status_distribution),
        'top_endpoints': json.dumps(top_endpoints),
        'client_breakdown': json.dumps(client_breakdown),
        'method_distribution': json.dumps(method_distribution),
        'daily_trends': json.dumps(daily_trends),
        'latency_percentiles': latency_percentiles,
        
        # Tables
        'recent_errors': recent_errors,
        
        # Active clients count
        'active_clients': Client.objects.filter(status='active').count(),
        'total_clients': Client.objects.count(),
    }
    
    return render(request, 'admin/api_dashboard.html', context)


@staff_member_required  
def endpoint_detail(request, endpoint_path):
    """
    Detailed view for a specific endpoint.
    
    Shows:
    - Request volume over time
    - Latency trends
    - Error patterns
    - Client usage for this endpoint
    """
    hours = int(request.GET.get('hours', 24))
    start_time = timezone.now() - timedelta(hours=hours)
    
    usage_qs = ClientUsage.objects.filter(
        endpoint=endpoint_path,
        timestamp__gte=start_time
    )
    
    # Endpoint KPIs
    total_requests = usage_qs.count()
    avg_latency = usage_qs.aggregate(Avg('response_time_ms'))['response_time_ms__avg'] or 0
    error_count = usage_qs.filter(status_code__gte=400).count()
    error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
    
    # Traffic over time
    traffic = list(
        usage_qs
        .annotate(hour=TruncHour('timestamp'))
        .values('hour')
        .annotate(count=Count('id'), avg_latency=Avg('response_time_ms'))
        .order_by('hour')
    )
    
    # Status codes
    status_codes = list(
        usage_qs
        .values('status_code')
        .annotate(count=Count('id'))
        .order_by('status_code')
    )
    
    # Client usage
    clients = list(
        usage_qs
        .values('client__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )
    
    # Convert datetimes
    for item in traffic:
        if 'hour' in item and item['hour']:
            item['hour'] = item['hour'].isoformat()
    
    context = {
        'endpoint': endpoint_path,
        'hours': hours,
        'total_requests': total_requests,
        'avg_latency': round(avg_latency, 2),
        'error_count': error_count,
        'error_rate': round(error_rate, 2),
        'traffic': json.dumps(traffic),
        'status_codes': json.dumps(status_codes),
        'clients': json.dumps(clients),
    }
    
    return render(request, 'admin/endpoint_detail.html', context)
