from django.urls import include, path
from rest_framework import routers

from . import views

app_name = "web"

router = routers.DefaultRouter()
router.register(r"home", views.HomeViewSet, basename="home")
router.register(r"routes", views.RoutesViewSet, basename="route")
router.register(r"stops", views.StopsViewSet, basename="stop")

urlpatterns = [
    path("", include(router.urls)),
]
