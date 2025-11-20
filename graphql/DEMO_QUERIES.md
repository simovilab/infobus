# GraphQL Demo Queries

This file contains ready-to-use GraphQL queries for testing and demonstration purposes. Copy and paste any query into GraphiQL at `http://localhost:8000/graphql/`.

## Basic Queries

### 1. Hello World
```graphql
query HelloWorld {
  hello {
    message
  }
}
```

### 2. List All Agencies
```graphql
query ListAgencies {
  agencies(page: 1, pageSize: 10) {
    edges {
      id
      agencyId
      agencyName
      agencyUrl
      agencyTimezone
      agencyPhone
      agencyEmail
    }
    pageInfo {
      totalCount
      hasNextPage
      pageNumber
      numPages
    }
  }
}
```

### 3. List All Stops with Pagination
```graphql
query ListStops {
  stops(page: 1, pageSize: 20) {
    edges {
      id
      stopId
      stopCode
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
      pageNumber
      numPages
    }
  }
}
```

### 4. List All Routes
```graphql
query ListRoutes {
  routes(page: 1, pageSize: 10) {
    edges {
      id
      routeId
      routeShortName
      routeLongName
      routeType
      routeColor
      routeTextColor
    }
    pageInfo {
      totalCount
      hasNextPage
    }
  }
}
```

### 5. List All Trips
```graphql
query ListTrips {
  trips(page: 1, pageSize: 20) {
    edges {
      id
      tripId
      tripHeadsign
      tripShortName
      directionId
      wheelchairAccessible
      bikesAllowed
    }
    pageInfo {
      totalCount
      hasNextPage
    }
  }
}
```

## Geographic Queries

### 6. Find Stops Near UCR (500m radius)
```graphql
query StopsNearUCR {
  stopsNear(lat: 9.9356, lon: -84.049, radiusKm: 0.5, page: 1, pageSize: 10) {
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

### 7. Find Stops Within 1km
```graphql
query StopsNear1km {
  stopsNear(lat: 9.9376, lon: -84.0514, radiusKm: 1.0, page: 1, pageSize: 20) {
    edges {
      stopId
      stopName
      stopLat
      stopLon
    }
    pageInfo {
      totalCount
    }
  }
}
```

## Nested Queries

### 8. Route with Agency and Trips
```graphql
query RouteDetails {
  route(id: 1) {
    routeShortName
    routeLongName
    routeColor
    agency {
      agencyName
      agencyPhone
      agencyEmail
    }
    trips {
      tripId
      tripHeadsign
      directionId
      wheelchairAccessible
    }
  }
}
```

### 9. Stop with Schedule and Routes
```graphql
query StopSchedule {
  stop(id: 1) {
    stopName
    stopLat
    stopLon
    wheelchairBoarding
    stopTimes {
      arrivalTime
      departureTime
      stopSequence
      trip {
        tripHeadsign
        route {
          routeShortName
          routeLongName
        }
      }
    }
    routes {
      routeShortName
      routeLongName
      routeColor
    }
  }
}
```

### 10. Trip with Full Context
```graphql
query TripFullContext {
  trip(id: 1) {
    tripId
    tripHeadsign
    directionId
    route {
      routeShortName
      routeLongName
      agency {
        agencyName
      }
    }
    service {
      monday
      tuesday
      wednesday
      thursday
      friday
      saturday
      sunday
      startDate
      endDate
    }
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
    geoshape {
      shapeName
      shapeFrom
      shapeTo
      hasAltitude
    }
  }
}
```

## Complex Nested Queries

### 11. Deep Nested: Route → Trips → Stops
```graphql
query DeepNestedRoute {
  route(id: 1) {
    routeShortName
    routeLongName
    agency {
      agencyName
      agencyUrl
    }
    trips {
      tripHeadsign
      directionId
      stops {
        stopName
        stopLat
        stopLon
        wheelchairBoarding
      }
    }
  }
}
```

### 12. Stop Times for Multiple Queries
```graphql
query ComplexStopTimes {
  stopTimesByTrip(tripId: 1, page: 1, pageSize: 20) {
    edges {
      stopSequence
      arrivalTime
      departureTime
      stop {
        stopName
      }
    }
    pageInfo {
      totalCount
    }
  }
  stopTimesByStop(stopId: 1, page: 1, pageSize: 20) {
    edges {
      arrivalTime
      departureTime
      trip {
        tripHeadsign
      }
    }
    pageInfo {
      totalCount
    }
  }
}
```

## Dashboard Query

### 13. Complete Dashboard (Multiple Entities)
```graphql
query Dashboard {
  gtfsProviders {
    providerId
    code
    name
    timezone
    isActive
  }
  agencies(page: 1, pageSize: 5) {
    edges {
      agencyName
      agencyUrl
    }
    pageInfo {
      totalCount
    }
  }
  routes(page: 1, pageSize: 5) {
    edges {
      routeShortName
      routeLongName
      routeColor
    }
    pageInfo {
      totalCount
    }
  }
  stops(page: 1, pageSize: 10) {
    edges {
      stopName
      stopLat
      stopLon
    }
    pageInfo {
      totalCount
    }
  }
  trips(page: 1, pageSize: 5) {
    edges {
      tripHeadsign
      directionId
    }
    pageInfo {
      totalCount
    }
  }
}
```

## Filtered Queries

### 14. Routes by Agency
```graphql
query RoutesByAgency {
  routesByAgency(agencyId: 1, page: 1, pageSize: 10) {
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
```

### 15. Trips by Route
```graphql
query TripsByRoute {
  tripsByRoute(routeId: 1, page: 1, pageSize: 10) {
    edges {
      tripId
      tripHeadsign
      directionId
      wheelchairAccessible
      bikesAllowed
    }
    pageInfo {
      totalCount
    }
  }
}
```

## GTFS Code Lookups

### 16. Lookup by GTFS Codes
```graphql
query CodeLookups {
  agencyByCode(agencyId: "bUCR", feedId: "costa-rica-gtfs") {
    id
    agencyName
    agencyUrl
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
    routeLongName
  }
}
```

## Performance Testing

### 17. Large Pagination Test
```graphql
query LargePagination {
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
      pageNumber
      numPages
      hasNextPage
    }
  }
}
```

### 18. Multiple Pages Test
```graphql
query MultiplePagesStops {
  page1: stops(page: 1, pageSize: 5) {
    edges {
      stopName
    }
    pageInfo {
      pageNumber
      totalCount
    }
  }
  page2: stops(page: 2, pageSize: 5) {
    edges {
      stopName
    }
    pageInfo {
      pageNumber
      totalCount
    }
  }
}
```

## Field Selection Demo

### 19. Minimal Fields (Fast)
```graphql
query MinimalStops {
  stops(page: 1, pageSize: 10) {
    edges {
      stopName
    }
    pageInfo {
      totalCount
    }
  }
}
```

### 20. Maximum Fields (Comprehensive)
```graphql
query MaximalStop {
  stop(id: 1) {
    id
    stopId
    stopCode
    stopName
    stopHeading
    stopDesc
    stopLat
    stopLon
    zoneId
    stopUrl
    locationType
    parentStation
    stopTimezone
    wheelchairBoarding
    platformCode
    shelter
    bench
    lit
    bay
    deviceChargingStation
    stopTimes {
      arrivalTime
      departureTime
    }
    routes {
      routeShortName
    }
  }
}
```

---

## Tips for Using These Queries

1. **Copy & Paste**: Select any query and paste directly into GraphiQL
2. **Modify Parameters**: Change `page`, `pageSize`, `id`, etc. to explore data
3. **Remove Fields**: Delete any fields you don't need - GraphQL flexibility!
4. **Combine Queries**: GraphQL supports multiple queries in one request
5. **Use Variables**: For production, use GraphQL variables instead of hardcoded values

## Testing Checklist

- [ ] Hello query works
- [ ] List queries return data with pagination
- [ ] Geographic search finds nearby stops
- [ ] Nested queries fetch related data
- [ ] Pagination metadata is correct
- [ ] Field selection returns only requested fields
- [ ] Error messages are clear for invalid queries

## Common Modifications

### Change Page Number
```graphql
stops(page: 2, pageSize: 10)  # Get page 2
```

### Adjust Page Size
```graphql
stops(page: 1, pageSize: 50)  # Get 50 items
```

### Change Geographic Radius
```graphql
stopsNear(lat: 9.9356, lon: -84.049, radiusKm: 2.0)  # 2km radius
```

### Select Different Fields
```graphql
stops {
  edges {
    stopName  # Only get stop names
  }
}
```

---

**Happy Querying!** 🚀

For more information, see the main [README.md](./README.md).
