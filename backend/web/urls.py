from django.urls import include, path
from rest_framework import routers

from . import views

app_name = "web"

router = routers.DefaultRouter()
router.register(r"home", views.HomeViewSet, basename="home")

urlpatterns = [
    path("", include(router.urls)),
]
