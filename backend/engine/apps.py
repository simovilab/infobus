from django.apps import AppConfig


class EngineConfig(AppConfig):
    """Tell Django to load the engine application using BigAutoField as its default primary-key type."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "engine"
