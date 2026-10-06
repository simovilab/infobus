from django.urls import include, path
from rest_framework import routers

from . import views

router = routers.DefaultRouter()
router.register(r"home", views.HomeViewSet)
router.register(r"routes", views.RoutesViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
