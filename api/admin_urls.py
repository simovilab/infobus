"""
URL configuration for admin dashboard views.
"""
from django.urls import path
from . import admin_dashboard

urlpatterns = [
    path('metrics/', admin_dashboard.admin_dashboard, name='admin_metrics_dashboard'),
    path('metrics/endpoint/<path:endpoint_path>/', admin_dashboard.endpoint_detail, name='admin_endpoint_detail'),
]
