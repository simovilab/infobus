from django.urls import path

from . import views

urlpatterns = [
    path("", views.screens, name="screens"),
    path("crear/", views.create_screen, name="create_screen"),
    path("<str:screen_id>/", views.screen, name="screen"),
    path("<str:screen_id>/editar/", views.edit_screen, name="edit_screen"),
]