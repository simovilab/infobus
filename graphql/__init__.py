"""
GraphQL API app for Infobús project.

Provides a GraphQL interface for GTFS transit data with support for:
- Queries across all GTFS entities
- Nested relationship traversal
- Pagination
- Geographic search (PostGIS)
"""

default_app_config = 'graphql.apps.GraphqlConfig'
