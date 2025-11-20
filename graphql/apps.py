"""
Django app configuration for GraphQL API.
"""
from django.apps import AppConfig


class GraphqlConfig(AppConfig):
    """Configuration for the GraphQL app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'graphql'
    verbose_name = 'GraphQL API'
    
    def ready(self):
        """
        Called when Django starts.
        Import signal handlers, register checks, etc. here if needed.
        """
        pass
