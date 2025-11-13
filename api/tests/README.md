# API Tests

This directory contains test suites for the Infobús API endpoints.

## Test Structure

### `test_schedule_departures.py`
Tests for the `/api/schedule/departures/` endpoint which provides scheduled departure information using the Data Access Layer (DAL).

**Test Cases:**
- `ScheduleDeparturesTests`: Complete test suite for the schedule departures endpoint
  - `test_returns_404_when_stop_missing`: Validates 404 error handling for non-existent stops
  - `test_returns_departures_with_expected_shape`: Validates response structure and data format

**What's Tested:**
- Endpoint returns proper HTTP status codes
- Response JSON structure matches API specification
- Required fields are present in response
- Time fields are formatted correctly (HH:MM:SS)
- Stop validation and error handling
- Integration with PostgreSQL via DAL
- Data enrichment (route names, trip information)

## Running Tests

### Run all API tests
```bash
docker compose exec web uv run python manage.py test api
```

### Run specific test file
```bash
docker compose exec web uv run python manage.py test api.tests.test_schedule_departures
```

### Run specific test class
```bash
docker compose exec web uv run python manage.py test api.tests.test_schedule_departures.ScheduleDeparturesTests
```

### Run specific test method
```bash
docker compose exec web uv run python manage.py test api.tests.test_schedule_departures.ScheduleDeparturesTests.test_returns_404_when_stop_missing
```

## Test Data

Tests use Django's test database which is created and destroyed automatically. Each test case sets up its own minimal test data using:
- `Feed.objects.create()` for GTFS feeds
- `Stop.objects.create()` for stop locations
- `StopTime.objects.bulk_create()` for scheduled stop times

## Test Dependencies

- `rest_framework.test.APITestCase`: Base class for API testing
- `django.test.TestCase`: Django test framework
- `gtfs.models`: GTFS data models (Feed, Stop, StopTime)
- PostgreSQL test database with PostGIS extension

## Coverage

Current test coverage focuses on:
- ✅ Schedule departures endpoint functionality
- ✅ Error handling and validation
- ✅ Response format verification
- ✅ DAL integration (PostgreSQL)

## Adding New Tests

When adding new API endpoint tests:
1. Create a new test file named `test_<feature>.py`
2. Import necessary test base classes and models
3. Add class-level and method-level docstrings
4. Set up minimal test data in `setUp()` method
5. Test both success and error cases
6. Validate response structure and data types
7. Update this README with the new test file information
