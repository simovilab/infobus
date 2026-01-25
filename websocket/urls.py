"""
WebSocket Demo URLs
"""
from django.urls import path
from . import views

app_name = 'websocket'

urlpatterns = [
    path('demo/trip/', views.trip_demo, name='trip_demo'),
    path('demo/status/', views.demo_status, name='demo_status'),
]
