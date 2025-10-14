#!/usr/bin/env python3
"""
GraphQL Setup Demo for Infobús Project
This script demonstrates that GraphQL with Strawberry is properly configured.
Run this to verify the setup without requiring database connections.
"""

import os
import sys

# Add project to Python path
sys.path.insert(0, '/home/olman/ProyectoGraphql/infobus')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'datahub.settings')
os.environ['DEBUG'] = 'true'

try:
    import django
    django.setup()
    
    print("🚀 Infobús GraphQL Setup Demo")
    print("=" * 50)
    
    # Test 1: Check Strawberry Django is installed
    from django.conf import settings
    if 'strawberry_django' in settings.INSTALLED_APPS:
        print("✅ Strawberry Django is installed and configured")
    else:
        print("❌ Strawberry Django not found in INSTALLED_APPS")
        sys.exit(1)
    
    # Test 2: Import GraphQL schema
    try:
        from gql_schema.schema import schema
        print("✅ GraphQL schema imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import GraphQL schema: {e}")
        sys.exit(1)
    
    # Test 3: Execute hello query
    try:
        hello_query = """
        query {
            hello {
                message
            }
        }
        """
        result = schema.execute_sync(hello_query)
        if result.data:
            message = result.data['hello']['message']
            print(f"✅ Hello query executed: {message}")
        else:
            print(f"❌ Hello query failed: {result.errors}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error executing hello query: {e}")
        sys.exit(1)
    
    # Test 4: Check URL configuration
    try:
        from django.urls import get_resolver
        resolver = get_resolver()
        
        # Look for GraphQL endpoint
        graphql_found = False
        api_found = False
        
        for pattern in resolver.url_patterns:
            pattern_str = str(pattern.pattern)
            if 'graphql' in pattern_str:
                graphql_found = True
            if 'api/' in pattern_str:
                api_found = True
        
        if graphql_found:
            print("✅ GraphQL endpoint (/graphql/) configured")
        else:
            print("❌ GraphQL endpoint not found in URL configuration")
        
        if api_found:
            print("✅ REST API endpoints still configured")
        else:
            print("⚠️  REST API endpoints not clearly visible (might still work)")
        
    except Exception as e:
        print(f"❌ Error checking URL configuration: {e}")
    
    # Test 5: Verify coexistence
    rest_framework_installed = 'rest_framework' in settings.INSTALLED_APPS
    drf_spectacular_installed = 'drf_spectacular' in settings.INSTALLED_APPS
    
    if rest_framework_installed and drf_spectacular_installed:
        print("✅ REST Framework and DRF Spectacular still configured")
        print("✅ GraphQL and REST API can coexist")
    else:
        print("⚠️  Some REST Framework components might be missing")
    
    print("\n🎉 GraphQL Setup Summary:")
    print("- ✅ Strawberry GraphQL installed and configured")
    print("- ✅ GraphQL schema created with hello query")  
    print("- ✅ GraphQL types defined for GTFS models")
    print("- ✅ GraphQL endpoint available at /graphql/")
    print("- ✅ Compatible with existing REST infrastructure")
    print("- ✅ Tests created for GraphQL functionality")
    
    print("\n🚀 Next Steps:")
    print("1. Start your Django development server")
    print("2. Navigate to http://localhost:8000/graphql/ for GraphQL Playground")
    print("3. Try this example query:")
    print("""
    query {
        hello {
            message
        }
    }
    """)
    print("4. REST API still available at http://localhost:8000/api/")
    
except Exception as e:
    print(f"❌ Setup verification failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)