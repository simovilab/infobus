"""
Custom test runner for Infobús that ensures PostgreSQL extensions are installed.
"""
from django.test.runner import DiscoverRunner
from django.db import connection


class InfobusTestRunner(DiscoverRunner):
    """Test runner that installs required PostgreSQL extensions in test database."""
    
    def setup_databases(self, **kwargs):
        """Set up test databases and install required extensions."""
        # Call parent to create databases
        result = super().setup_databases(**kwargs)
        
        # Install required PostgreSQL extensions
        with connection.cursor() as cursor:
            # PostGIS (should already be enabled, but ensure it)
            cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
            
            # pg_trgm for trigram similarity searches
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            
            print("✓ PostgreSQL extensions installed in test database")
        
        return result
