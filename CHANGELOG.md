# Changelog

All notable changes to the Infobús project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **GraphQL API** (`/gql/` endpoint)
  - Modern GraphQL interface for GTFS transit data queries
  - Built with Strawberry GraphQL 0.285+ and Strawberry Django
  - Interactive GraphiQL browser interface for API exploration
  - 8 GraphQL types covering all major GTFS entities (GTFSProvider, Agency, Stop, Route, Trip, StopTime, Calendar, GeoShape)
  - 20+ query resolvers with multiple access patterns
  - Pagination support using Connection pattern with PageInfo metadata
  - Nested query capability (e.g., routes → trips → stops in one request)
  - Geographic search using PostGIS spatial queries (`stopsNear` resolver)
  - GTFS code lookups for external system integration
  - Performance optimized with ORM query optimization (`select_related`, `prefetch_related`)
  - Self-documenting via GraphQL introspection
  - Comprehensive test suite (219 lines) with query execution, schema validation, and pagination tests

- **GraphQL Documentation** (`gql/README.md`)
  - Complete API reference with 750+ lines of documentation
  - Query examples for all resolvers (basic lookups, pagination, code lookups, geographic search, filtered queries, nested queries)
  - Integration examples in Python, JavaScript, and cURL
  - Performance optimization guidelines
  - GraphQL vs REST comparison and use case recommendations
  - Troubleshooting guide
  - Architecture and technology stack documentation

- **Demo Queries** (`gql/DEMO_QUERIES.md`)
  - Curated collection of real-world GraphQL query examples
  - Basic to advanced query patterns
  - Geographic search demos
  - Complex nested query examples
  - Ready-to-paste queries for testing

- **GraphQL Test Suite** (`gql/tests.py`)
  - Comprehensive test coverage (219 lines)
  - Query execution validation
  - Schema structure tests
  - Endpoint accessibility tests
  - GTFS model fixtures
  - Error handling tests
  - Pagination functionality tests

### Fixed
- App naming conflict resolution by renaming `graphql/` to `gql/` to avoid import collision with Python's `graphql-core` library

### Technical Implementation
- **Schema Architecture** (`gql/schema.py`)
  - Strawberry Schema definition with Query type registration
  - Integration with Django URL routing
  
- **Type Definitions** (`gql/types.py`, 271 lines)
  - Strawberry Django model types with proper field mappings
  - Custom pagination types (Connection, PageInfo)
  - Relationship fields for nested queries
  
- **Query Resolvers** (`gql/queries.py`, 265 lines)
  - Basic entity lookups by ID
  - Paginated list queries
  - GTFS code-based lookups
  - Geographic proximity search
  - Filtered queries by relationships
  - Optimized with `select_related()` and `prefetch_related()`

- **Django Integration**
  - Django app configuration (`gql/apps.py`)
  - URL routing in `datahub/urls.py`
  - GraphiQL interface enabled in development
  - ASGI/Daphne server compatibility

### Dependencies Added
- `strawberry-graphql==0.285.0` - GraphQL schema definition library
- `strawberry-graphql[django]==0.285.0` - Django integration for Strawberry
- Updated `uv.lock` with new dependencies and dependency tree

### Configuration
- GraphQL endpoint configured at `/gql/`
- GraphiQL interface accessible in browser (development mode)
- ASGI server compatibility maintained
- No additional environment variables required

### Files Added
- `gql/__init__.py` - Django app initialization
- `gql/apps.py` - Django app configuration
- `gql/schema.py` - Main GraphQL schema definition
- `gql/types.py` - GraphQL type definitions (271 lines)
- `gql/queries.py` - Query resolvers (265 lines)
- `gql/tests.py` - Test suite (219 lines)
- `gql/README.md` - Complete API documentation (750+ lines)
- `gql/DEMO_QUERIES.md` - Demo query collection
- `demo_graphql.py` - Python integration example script

### Files Modified
- `datahub/settings.py` - Added `gql.apps.GqlConfig` to INSTALLED_APPS
- `datahub/urls.py` - Added GraphQL endpoint routing
- `pyproject.toml` - Added Strawberry GraphQL dependencies
- `uv.lock` - Updated with GraphQL dependencies

## Future Enhancements
- Mutations for data modification (currently read-only)
- Real-time subscriptions for live data updates
- Authentication and authorization integration
- Query complexity limits and depth restrictions
- DataLoader integration for batch loading optimization
- Rate limiting specific to GraphQL endpoint
- Metrics and monitoring for GraphQL queries
