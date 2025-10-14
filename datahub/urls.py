"""
URL configuration for datahub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse

def health_check(request):
    """Simple health check endpoint for container health monitoring."""
    return HttpResponse("OK", content_type="text/plain")

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("admin/", admin.site.urls),
    path("", include("website.urls")),
    path("api/", include("api.urls")),
    path("gtfs/", include("gtfs.urls")),
    path("status/", include("feed.urls")),
    path("alertas/", include("alerts.urls")),
]
