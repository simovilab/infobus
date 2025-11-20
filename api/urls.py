from django.urls import include, path
from rest_framework import routers
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator

from . import views
from .auth_views import CustomTokenObtainPairView, CustomTokenRefreshView, register, profile

# Helper to conditionally require admin for docs in production
# In production (DEBUG=False), require is_staff; in dev, allow all
def get_doc_view(view_class, **kwargs):
    if settings.DEBUG:
        return view_class.as_view(**kwargs)
    else:
        # In production, require Django session auth with is_staff
        return user_passes_test(lambda u: u.is_staff, login_url='/admin/login/')(view_class.as_view(**kwargs))

router = routers.DefaultRouter()
router.register(r"info-services", views.InfoServiceViewSet)
router.register(r"gtfs-providers", views.GTFSProviderViewSet)
router.register(r"agencies", views.AgencyViewSet)
router.register(r"stops", views.StopViewSet)
router.register(r"geo-stops", views.GeoStopViewSet, basename="geo-stop")
router.register(r"shapes", views.ShapeViewSet)
router.register(r"geo-shapes", views.GeoShapeViewSet)
router.register(r"routes", views.RouteViewSet)
router.register(r"calendars", views.CalendarViewSet)
router.register(r"calendar-dates", views.CalendarDateViewSet)
router.register(r"trips", views.TripViewSet)
router.register(r"stop-times", views.StopTimeViewSet)
router.register(r"fare-attributes", views.FareAttributeViewSet)
router.register(r"fare-rules", views.FareRuleViewSet)
router.register(r"feed-info", views.FeedInfoViewSet)
router.register(r"alerts", views.ServiceAlertViewSet)
router.register(r"feed-messages", views.FeedMessageViewSet)
router.register(r"stop-time-updates", views.StopTimeUpdateViewSet)


# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path("", views.api_root, name='api-root'),
    path("", include(router.urls)),
    
    # Authentication endpoints
    path("auth/register/", register, name="auth-register"),
    path("auth/login/", CustomTokenObtainPairView.as_view(), name="auth-login"),
    path("auth/refresh/", CustomTokenRefreshView.as_view(), name="auth-refresh"),
    path("auth/profile/", profile, name="auth-profile"),
    
    # API endpoints
    path("next-trips/", views.NextTripView.as_view(), name="next-trips"),
    path("next-stops/", views.NextStopView.as_view(), name="next-stops"),
    path("route-stops/", views.RouteStopView.as_view(), name="route-stops"),
    path("schedule/departures/", views.ScheduleDeparturesView.as_view(), name="schedule-departures"),
    path("arrivals/", views.ArrivalsView.as_view(), name="arrivals"),
    path("status/", views.StatusView.as_view(), name="status"),
    path("search/", views.SearchView.as_view(), name="search"),
    path("health/", views.HealthView.as_view(), name="health"),
    path("ready/", views.ReadyView.as_view(), name="ready"),
    
    # Framework endpoints
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    # API Documentation (restricted to staff users in production, open in dev)
    path("docs/schema/", get_doc_view(SpectacularAPIView), name="schema"),
    path("docs/", get_doc_view(SpectacularRedocView, url_name="schema"), name="api_docs"),
    path("docs/swagger/", get_doc_view(SpectacularSwaggerView, url_name="schema"), name="swagger-ui"),
]
