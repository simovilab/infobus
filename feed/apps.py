from django.apps import AppConfig


class FeedConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "feed"

    def ready(self):
        """Import metrics when Django starts to register them with Prometheus."""
        from feed import metrics  # noqa: F401
