from django.urls import include, path
from rest_framework import routers
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView

from . import views

router = routers.DefaultRouter()
router.register(r"info-service", views.InfoServiceViewSet, basename="info-service")
router.register(r"gtfs-providers", views.GTFSProviderViewSet)
router.register(r"agencies", views.AgencyViewSet)
router.register(r"stops", views.StopViewSet)
router.register(r"geo-stops", views.GeoStopViewSet, basename="geo-stop")
router.register(r"shapes", views.ShapeViewSet)
router.register(r"geo-shapes", views.GeoShapeViewSet)
router.register(r"geoshapes", views.GeoShapeViewSet, basename="geoshapes")
router.register(r"routes", views.RouteViewSet)
router.register(r"calendar", views.CalendarViewSet, basename="calendar")
router.register(r"calendar-dates", views.CalendarDateViewSet)
router.register(r"trips", views.TripViewSet)
router.register(r"stop-times", views.StopTimeViewSet)
router.register(r"fare-attributes", views.FareAttributeViewSet)
router.register(r"fare-rules", views.FareRuleViewSet)
router.register(r"feed-info", views.FeedInfoViewSet)
router.register(r"vehicle-positions", views.VehiclePositionViewSet)
router.register(r"trip-updates", views.TripUpdateViewSet)
router.register(r"service-alerts", views.ServiceAlertViewSet)
router.register(r"weather", views.WeatherViewSet)
router.register(r"social", views.SocialViewSet)


# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("", include(router.urls)),
    path("trip-times/", views.TripTimesView.as_view(), name="trip-times"),
    path("next-trips/", views.NextTripView.as_view(), name="next-trips"),
    path("next-stops/", views.NextStopView.as_view(), name="next-stops"),
    path("route-stops/", views.RouteStopView.as_view(), name="route-stops"),
    path("wide-alerts/", views.WideAlertsView.as_view(), name="wide-alerts"),
    path("user-reports/", views.UserReportsView.as_view(), name="user-reports"),
    path("user-data/", views.UserDataView.as_view(), name="user-data"),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("docs/schema/", views.get_schema, name="schema"),
    path("docs/", SpectacularRedocView.as_view(url_name="schema"), name="api_docs"),
]
