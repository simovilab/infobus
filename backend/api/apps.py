from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Tell Django to load the API application using BigAutoField as its default primary-key type."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"
