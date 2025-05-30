from django.urls import path

from . import views

urlpatterns = [
<<<<<<< HEAD
    path("", views.feed),
]
=======
    path("", views.status, name="status"),
]
>>>>>>> fe8afcdb6c3425233286364f12d1774bf5288c9f
