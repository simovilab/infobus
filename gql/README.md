# GraphQL API Documentation

## Overview

The GraphQL API provides a flexible, modern interface to query Infobús GTFS (General Transit Feed Specification) transit data. Built with [Strawberry GraphQL](https://strawberry.rocks/), it offers an alternative to the REST API with support for nested queries, field selection, and real-time exploration via GraphiQL.

## Quick Start

### Access the API

- **Endpoint:** `http://localhost:8000/gql/`
- **Interactive Interface:** Open the URL in a browser to access GraphiQL
- **Method:** POST (for programmatic access)
- **Content-Type:** `application/json`

### Your First Query

Open `http://localhost:8000/gql/` in your browser and try:

```graphql
query {
  hello {
    message
  }
}
```

Expected response:
```json
{
  "data": {
    "hello": {
      "message": "¡Hola desde GraphQL de Infobús!"
    }
  }
}
```

## Features

- ✅ **8 GraphQL Types** covering all major GTFS entities
- ✅ **20+ Query Resolvers** with multiple access patterns
- ✅ **Pagination** using the Connection pattern
- ✅ **Nested Queries** (e.g., routes → trips → stops in one request)
- ✅ **Geographic Search** using PostGIS spatial queries
- ✅ **GTFS Code Lookups** for integration with external systems
- ✅ **Performance Optimized** with ORM query optimization
- ✅ **Self-Documenting** via GraphQL introspection

## GraphQL Types

### Core GTFS Entities

#### 1. **GTFSProviderType**
Transit data providers (organizations that publish GTFS data).

**Fields:**
- `providerId`: Provider database ID
- `code`: Short code (e.g., "CTP", "TUASA")
- `name`: Full provider name
- `timezone`: Timezone (e.g., "America/Costa_Rica")
- `isActive`: Whether provider is currently active

#### 2. **AgencyType**
Transit agencies that operate routes.

**Fields:**
- `id`, `agencyId`: Identifiers
- `agencyName`: Agency name (e.g., "Buses de la Universidad de Costa Rica")
- `agencyUrl`: Agency website
- `agencyTimezone`: Operating timezone
- `agencyPhone`, `agencyEmail`: Contact information

#### 3. **StopType**
Bus stops and stations.

**Fields:**
- `id`, `stopId`, `stopCode`: Identifiers
- `stopName`: Stop name
- `stopLat`, `stopLon`: Geographic coordinates (WGS84)
- `wheelchairBoarding`: Accessibility status
- `shelter`, `bench`, `lit`: Amenities
- `platformCode`, `bay`: Physical location details

**Relationships:**
- `stopTimes`: List of scheduled stop times
- `routes`: Routes serving this stop

#### 4. **RouteType**
Bus routes.

**Fields:**
- `id`, `routeId`: Identifiers
- `routeShortName`: Short route name (e.g., "L1")
- `routeLongName`: Full route description
- `routeType`: GTFS route type (3 = bus)
- `routeColor`, `routeTextColor`: Display colors

**Relationships:**
- `agency`: Operating agency
- `trips`: All trips for this route
- `stops`: All stops served by this route

#### 5. **TripType**
Individual trip instances.

**Fields:**
- `id`, `tripId`: Identifiers
- `tripHeadsign`: Destination displayed on vehicle
- `directionId`: 0 = outbound, 1 = inbound
- `wheelchairAccessible`, `bikesAllowed`: Accessibility

**Relationships:**
- `route`: Route this trip belongs to
- `service`: Service calendar (when trip runs)
- `stopTimes`: Scheduled times at each stop
- `stops`: Stops in sequence order
- `geoshape`: GPS path of trip

#### 6. **StopTimeType**
Scheduled arrival/departure at a stop.

**Fields:**
- `id`, `tripId`, `stopId`: Identifiers
- `arrivalTime`, `departureTime`: Times (HH:MM:SS format)
- `stopSequence`: Order of stop in trip (1, 2, 3...)
- `pickupType`, `dropOffType`: Boarding rules
- `timepoint`: Whether time is exact or approximate

**Relationships:**
- `trip`: Trip this time belongs to
- `stop`: Stop where this occurs

#### 7. **CalendarType**
Service schedule (which days service runs).

**Fields:**
- `id`, `serviceId`: Identifiers
- `monday`, `tuesday`, ..., `sunday`: Boolean for each day
- `startDate`, `endDate`: Validity period

**Relationships:**
- `trips`: Trips using this schedule

#### 8. **GeoShapeType**
GPS path/shape of a route.

**Fields:**
- `id`, `shapeId`: Identifiers
- `shapeName`, `shapeDesc`: Description
- `shapeFrom`, `shapeTo`: Endpoints
- `hasAltitude`: Whether elevation data included

**Relationships:**
- `trips`: Trips following this path

### Pagination Types

All list queries return a **Connection** type with pagination metadata:

```graphql
type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
  totalCount: Int!
  pageNumber: Int!
  numPages: Int!
}
```

## Query Reference

### Hello Query (Test)

```graphql
query {
  hello {
    message
  }
}
```

### Basic Entity Lookups

Get a single entity by database ID:

```graphql
# Get agency by ID
query {
  agency(id: 1) {
    agencyName
    agencyUrl
  }
}

# Get stop by ID
query {
  stop(id: 1) {
    stopName
    stopLat
    stopLon
  }
}

# Get route by ID
query {
  route(id: 1) {
    routeShortName
    routeLongName
  }
}

# Get trip by ID
query {
  trip(id: 1) {
    tripHeadsign
    directionId
  }
}
```

### Paginated Lists

Get multiple entities with pagination:

```graphql
# Get agencies (paginated)
query {
  agencies(page: 1, pageSize: 10) {
    edges {
      id
      agencyName
      agencyUrl
    }
    pageInfo {
      totalCount
      hasNextPage
      pageNumber
      numPages
    }
  }
}

# Get stops (paginated)
query {
  stops(page: 1, pageSize: 20) {
    edges {
      stopId
      stopName
      stopLat
      stopLon
      wheelchairBoarding
    }
    pageInfo {
      totalCount
      hasNextPage
    }
  }
}

# Get routes (paginated)
query {
  routes(page: 1, pageSize: 10) {
    edges {
      routeShortName
      routeLongName
      routeColor
    }
    pageInfo {
      totalCount
    }
  }
}

# Get trips (paginated)
query {
  trips(page: 1, pageSize: 50) {
    edges {
      tripId
      tripHeadsign
      directionId
    }
    pageInfo {
      totalCount
      hasNextPage
    }
  }
}

# Get stop times (paginated)
query {
  stopTimes(page: 1, pageSize: 100) {
    edges {
      tripId
      stopId
      arrivalTime
      departureTime
      stopSequence
    }
    pageInfo {
      totalCount
    }
  }
}
```

### GTFS Code Lookups

Look up entities by their GTFS codes (useful for integration):

```graphql
query {
  agencyByCode(agencyId: "bUCR", feedId: "costa-rica-gtfs") {
    id
    agencyName
  }
  
  stopByCode(stopId: "bUCR_0_01", feedId: "costa-rica-gtfs") {
    id
    stopName
    stopLat
    stopLon
  }
  
  routeByCode(routeId: "bUCR_L1", feedId: "costa-rica-gtfs") {
    id
    routeShortName
  }
  
  tripByCode(tripId: "desde_educacion_sin_milla_entresemana_06:10", feedId: "costa-rica-gtfs") {
    id
    tripHeadsign
  }
}
```

### Geographic Search

Find stops near a location using PostGIS spatial queries:

```graphql
# Find stops within 500m of UCR main campus
query {
  stopsNear(
    lat: 9.9356
    lon: -84.049
    radiusKm: 0.5
    page: 1
    pageSize: 10
  ) {
    edges {
      stopName
      stopLat
      stopLon
      wheelchairBoarding
      shelter
      bench
      lit
    }
    pageInfo {
      totalCount
      hasNextPage
    }
  }
}
```

### Filtered Queries

Get entities filtered by relationships:

```graphql
# Get all routes for a specific agency
query {
  routesByAgency(agencyId: 1, page: 1, pageSize: 20) {
    edges {
      routeShortName
      routeLongName
    }
    pageInfo {
      totalCount
    }
  }
}

# Get all trips for a specific route
query {
  tripsByRoute(routeId: 1, page: 1, pageSize: 20) {
    edges {
      tripHeadsign
      directionId
    }
    pageInfo {
      totalCount
    }
  }
}

# Get stop times for a specific trip
query {
  stopTimesByTrip(tripId: 1, page: 1, pageSize: 50) {
    edges {
      stopSequence
      arrivalTime
      departureTime
    }
    pageInfo {
      totalCount
    }
  }
}

# Get stop times for a specific stop
query {
  stopTimesByStop(stopId: 1, page: 1, pageSize: 50) {
    edges {
      arrivalTime
      departureTime
    }
    pageInfo {
      totalCount
    }
  }
}
```

### Nested Queries

One of GraphQL's most powerful features - get related data in a single request:

```graphql
# Get route with all its relationships
query {
  route(id: 1) {
    routeShortName
    routeLongName
    routeColor
    
    # Nested: Get operating agency
    agency {
      agencyName
      agencyPhone
      agencyEmail
    }
    
    # Nested: Get all trips for this route
    trips {
      tripHeadsign
      directionId
      wheelchairAccessible
      
      # Double-nested: Get stops for each trip
      stops {
        stopName
        stopLat
        stopLon
      }
    }
    
    # Nested: Get all unique stops served by route
    stops {
      stopName
      stopLat
      stopLon
    }
  }
}
```

```graphql
# Get stop with schedule information
query {
  stop(id: 1) {
    stopName
    stopLat
    stopLon
    wheelchairBoarding
    
    # Nested: Get all stop times at this stop
    stopTimes {
      arrivalTime
      departureTime
      
      # Double-nested: Get trip information
      trip {
        tripHeadsign
        
        # Triple-nested: Get route information
        route {
          routeShortName
          routeLongName
        }
      }
    }
    
    # Nested: Get all routes serving this stop
    routes {
      routeShortName
      routeLongName
      routeColor
    }
  }
}
```

```graphql
# Complex nested query: Trip with full context
query {
  trip(id: 1) {
    tripId
    tripHeadsign
    directionId
    
    # Route information
    route {
      routeShortName
      routeLongName
      agency {
        agencyName
      }
    }
    
    # Service schedule
    service {
      monday tuesday wednesday thursday friday saturday sunday
      startDate
      endDate
    }
    
    # All stops in order
    stopTimes {
      stopSequence
      arrivalTime
      departureTime
      stop {
        stopName
        stopLat
        stopLon
      }
    }
    
    # GPS shape
    geoshape {
      shapeName
      shapeFrom
      shapeTo
    }
  }
}
```

## Testing

### Run Test Suite

```bash
# Run all GraphQL tests
python manage.py test gql

# Run with verbose output
python manage.py test gql --verbosity=2

# Run specific test class
python manage.py test gql.tests.GraphQLTestCase
```

### Test Coverage

The test suite (`gql/tests.py`) includes:
- Query execution tests
- Schema validation
- Endpoint accessibility
- GTFS model fixtures
- Error handling
- Pagination tests

## Performance Considerations

### Query Optimization

The GraphQL resolvers use Django ORM optimizations:

- **`select_related()`**: Eager loading for foreign keys (prevents N+1 queries)
- **`prefetch_related()`**: Efficient loading of reverse relationships
- **Proper indexing**: Database indexes on frequently queried fields
- **Pagination**: Limits result set size

### Best Practices

1. **Use pagination** for list queries with large datasets
2. **Request only needed fields** - GraphQL's strength is selective fetching
3. **Limit nesting depth** - Deep nested queries can be expensive
4. **Use filters** - `routesByAgency` is more efficient than fetching all routes

## Integration Examples

### Python with `requests`

```python
import requests

GRAPHQL_URL = "http://localhost:8000/gql/"

query = """
query {
  stops(page: 1, pageSize: 5) {
    edges {
      stopName
      stopLat
      stopLon
    }
    pageInfo {
      totalCount
    }
  }
}
"""

response = requests.post(
    GRAPHQL_URL,
    json={"query": query},
    headers={"Content-Type": "application/json"}
)

data = response.json()
print(data["data"]["stops"])
```

### JavaScript with `fetch`

```javascript
const GRAPHQL_URL = "http://localhost:8000/gql/";

const query = `
  query {
    stopsNear(lat: 9.9356, lon: -84.049, radiusKm: 0.5) {
      edges {
        stopName
        stopLat
        stopLon
      }
      pageInfo {
        totalCount
      }
    }
  }
`;

fetch(GRAPHQL_URL, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ query })
})
  .then(res => res.json())
  .then(data => console.log(data.data.stopsNear));
```

### cURL

```bash
curl -X POST http://localhost:8000/gql/ \
  -H "Content-Type: application/json" \
  -d '{
    "query": "query { hello { message } }"
  }'
```

## GraphQL vs REST

### When to Use GraphQL

✅ **Use GraphQL when:**
- You need nested/related data (routes → trips → stops)
- Different clients need different fields
- You want to minimize API calls
- You need flexible querying without new endpoints

### When to Use REST

✅ **Use REST when:**
- Simple CRUD operations
- File uploads/downloads
- Caching is critical (HTTP caching)
- Legacy client compatibility

**Note:** Both APIs coexist in Infobús - use the right tool for each use case!

## Troubleshooting

### GraphiQL Shows "Forbidden (403)"

This is expected for POST requests without CSRF token. Use the **browser-based GraphiQL interface** (GET request) instead, which works without CSRF.

### "Cannot query field X on type Y"

Check the schema documentation in GraphiQL (Docs panel on the right) to see available fields.

### Slow Queries

1. Use pagination to limit result sizes
2. Avoid deeply nested queries
3. Request only needed fields
4. Check database indexes

### Import Errors

Ensure `graphql` app is in `INSTALLED_APPS` in `settings.py`:
```python
INSTALLED_APPS = [
    ...
    "gql.apps.GqlConfig",
    "strawberry_django",
    ...
]
```

## Architecture

### Project Structure

```
gql/
├── __init__.py       # App configuration
├── apps.py           # Django app config class
├── schema.py         # Main GraphQL schema
├── types.py          # GraphQL type definitions (271 lines)
├── queries.py        # Query resolvers (265 lines)
├── tests.py          # Test suite (219 lines)
└── README.md         # This file
```

### Technology Stack

- **Framework:** Django 5.2+
- **GraphQL Library:** Strawberry GraphQL 0.285+
- **Database:** PostgreSQL 16 + PostGIS 3.4
- **ORM:** Django ORM with GeoDjango
- **ASGI Server:** Daphne 4.2+

## Further Reading

- [Strawberry GraphQL Documentation](https://strawberry.rocks/)
- [GraphQL Official Spec](https://graphql.org/)
- [GTFS Static Reference](https://gtfs.org/schedule/)
- [PostGIS Documentation](https://postgis.net/documentation/)

## Support

For issues or questions:
1. Check the GraphiQL interface documentation (Docs panel)
2. Review this README
3. Check the test suite for usage examples
4. Consult project documentation

---

**Last Updated:** November 2025  
**GraphQL API Version:** 1.0  
**Maintainer:** Infobús Development Team
