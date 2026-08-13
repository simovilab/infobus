from django.apps import AppConfig


class WebsiteConfig(AppConfig):
    """Tell Django to load the website application using BigAutoField as its default primary-key type."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "website"
