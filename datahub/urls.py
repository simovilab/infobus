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
<<<<<<< HEAD
=======

>>>>>>> fe8afcdb6c3425233286364f12d1774bf5288c9f
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
<<<<<<< HEAD
    path("", include("website.urls"), name="index"),
    path("api/", include("api.urls"), name="api"),
    path("gtfs/", include("gtfs.urls"), name="gtfs_page"),
    path("feed/", include("feed.urls"), name="feed_page"),
    path("pantallas/", include("alerts.urls"), name="alerts_page"),
=======
    path("", include("website.urls")),
    path("api/", include("api.urls")),
    path("gtfs/", include("gtfs.urls")),
    path("status/", include("feed.urls")),
    path("alertas/", include("alerts.urls")),
>>>>>>> fe8afcdb6c3425233286364f12d1774bf5288c9f
]
