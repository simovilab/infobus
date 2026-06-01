from django.urls import path

from . import views

urlpatterns = [
    path("parada/<str:stop_slug>/", views.stop_screen, name="stop_screen"),
]
