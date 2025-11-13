# Changelog

All notable changes to the Infobús project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - Storage and Data Access Layer (feat/storage-reading-dal)

#### Storage Layer
- **Data Access Layer (DAL)** with repository pattern for GTFS schedule data
  - `ScheduleRepository` interface defining contract for schedule data access
  - `PostgresScheduleRepository` implementation using Django ORM
  - `CachedScheduleRepository` decorator for Redis caching with configurable TTL
  - `RedisCacheProvider` for cache operations
  - Factory pattern (`get_schedule_repository()`) for obtaining configured repository instances

#### API Endpoints
- **GET /api/schedule/departures/** - Retrieve scheduled departures for a stop
  - Query parameters:
    - `stop_id` (required): Stop identifier
    - `feed_id` (optional): Feed identifier, defaults to current feed
    - `date` (optional): Service date in YYYY-MM-DD format, defaults to today
    - `time` (optional): Departure time in HH:MM or HH:MM:SS format, defaults to now
    - `limit` (optional): Maximum number of results (1-100), defaults to 10
  - Returns enriched departure data with route information:
    - Route short name and long name
    - Trip headsign and direction
    - Formatted arrival and departure times (HH:MM:SS)
  - Validates stop existence (returns 404 if not found)
  - Uses PostgreSQL as data source with Redis read-through caching

#### Configuration
- `SCHEDULE_CACHE_TTL_SECONDS` environment variable for cache duration (default: 60 seconds)
- Cache key format: `schedule:next_departures:feed={FEED_ID}:stop={STOP_ID}:date={YYYY-MM-DD}:time={HHMMSS}:limit={N}:v1`

#### Testing
- Comprehensive test suite for schedule departures endpoint
  - Response structure validation
  - Stop validation (404 handling)
  - Time format validation (HH:MM:SS)
  - Programmatic test dataset creation

#### Documentation
- OpenAPI/Swagger schema generation with drf-spectacular
- API endpoint annotations for automatic documentation
- Architecture documentation for DAL strategy
- README updates with endpoint usage examples and cache configuration

### Removed - Storage and Data Access Layer (feat/storage-reading-dal)

#### Fuseki Implementation
- Removed Apache Jena Fuseki as optional SPARQL backend
  - Deleted `storage/fuseki_schedule.py` implementation
  - Removed `api/tests/test_fuseki_schedule.py` integration tests
  - Removed Fuseki Docker service from docker-compose.yml
  - Deleted `fuseki_data` Docker volume
  - Removed `docker/fuseki/` configuration directory
  - Deleted `docs/dev/fuseki.md` documentation
- Removed Fuseki-related configuration
  - `FUSEKI_ENABLED` environment variable
  - `FUSEKI_ENDPOINT` environment variable
  - Fuseki references in `.env.local.example`
- Updated `storage/factory.py` to use only PostgreSQL repository
- PostgreSQL with Redis caching is now the sole storage backend

### Changed - Storage and Data Access Layer (feat/storage-reading-dal)

#### Documentation
- Updated README.md to document new DAL architecture and API endpoints
- Updated docs/architecture.md with storage strategy and repository pattern
- Added project structure documentation including `storage/` directory
- Removed all Fuseki references from documentation

---

## [Previous Releases]

<!-- Future releases will be documented above this line -->
