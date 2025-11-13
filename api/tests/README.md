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

### `test_arrivals.py`
Tests for the `/api/arrivals/` endpoint which provides real-time arrival predictions from an external ETA service (Project 4).

**Test Cases:**
- `ArrivalsEndpointTests`: Complete test suite for the arrivals endpoint
  - `test_arrivals_returns_expected_shape`: Validates response structure with mocked upstream
  - `test_arrivals_propagates_upstream_error`: Validates 502 error on upstream failure
  - `test_arrivals_requires_stop_id`: Validates 400 error when stop_id missing
  - `test_arrivals_accepts_wrapped_results_object`: Validates handling of {"results": [...]} format
  - `test_arrivals_handles_unexpected_upstream_structure_as_empty_list`: Validates graceful degradation
  - `test_arrivals_limit_bounds_low`: Validates limit minimum (1)
  - `test_arrivals_limit_bounds_high`: Validates limit maximum (100)
  - `test_arrivals_limit_must_be_integer`: Validates limit parameter type
  - `test_arrivals_returns_501_if_not_configured`: Validates 501 when ETAS_API_URL not set

**What's Tested:**
- Endpoint returns proper HTTP status codes
- Response JSON structure matches API specification
- Required fields present (trip_id, route info, times, wheelchair_accessible)
- Time fields formatted correctly (HH:MM:SS)
- Parameter validation (stop_id required, limit bounds)
- Error propagation from upstream service (502 on failure)
- Configuration validation (501 when not configured)
- Upstream response format handling (wrapped/unwrapped arrays)
- Mocked HTTP requests using `unittest.mock`

## Running Tests

### Run all API tests
```bash
docker compose exec web uv run python manage.py test api
```

### Run specific test file
```bash
# Schedule departures tests
docker compose exec web uv run python manage.py test api.tests.test_schedule_departures

# Arrivals tests
docker compose exec web uv run python manage.py test api.tests.test_arrivals
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

### Database Tests
Tests use Django's test database which is created and destroyed automatically. Each test case sets up its own minimal test data using:
- `Feed.objects.create()` for GTFS feeds
- `Stop.objects.create()` for stop locations
- `StopTime.objects.bulk_create()` for scheduled stop times

### External Service Tests
Tests that integrate with external services use mocked HTTP responses:
- `unittest.mock.patch` to mock `requests.get()` calls
- Mock objects configured to return predefined responses
- No actual network calls during testing

## Test Dependencies

- `rest_framework.test.APITestCase`: Base class for API testing
- `django.test.TestCase`: Django test framework
- `unittest.mock`: Mocking external HTTP requests
- `gtfs.models`: GTFS data models (Feed, Stop, StopTime)
- PostgreSQL test database with PostGIS extension

## Coverage

Current test coverage focuses on:
- ✅ Schedule departures endpoint (PostgreSQL/DAL)
- ✅ Real-time arrivals endpoint (external ETA service integration)
- ✅ Error handling and validation
- ✅ Response format verification
- ✅ Parameter validation (required fields, bounds checking)
- ✅ External service error propagation
- ✅ Configuration validation

## Adding New Tests

When adding new API endpoint tests:
1. Create a new test file named `test_<feature>.py`
2. Import necessary test base classes and models
3. Add class-level and method-level docstrings
4. Set up minimal test data in `setUp()` method
5. Test both success and error cases
6. Validate response structure and data types
7. Update this README with the new test file information
