# API

The `api` Django app is Infobús®'s HTTP serialization boundary. It exposes
selected `feed` Schedule models, the `engine.InfoService` model, three
read-oriented query views, browsable-API authentication routes, and Redoc
documentation under the project-level `/api/` prefix
(`backend/infobus/urls.py:32`, `backend/api/urls.py:8`,
`backend/api/urls.py:22`, `backend/api/urls.py:29`,
`backend/api/urls.py:34`).

The app is stateless in the application-ownership sense: it defines no model
of its own and delegates all persisted data to `feed` or `engine`
(`backend/api/models.py:1`, `backend/api/models.py:3`,
`backend/api/views.py:3`, `backend/api/views.py:4`).

## Purpose

The app has four connected purposes:

1. Publish mutable REST resources for 14 `feed` Schedule model projections
   and one `engine.InfoService` projection through a DRF `DefaultRouter`
   (`backend/api/urls.py:7`, `backend/api/urls.py:8`,
   `backend/api/urls.py:9`, `backend/api/urls.py:22`).
2. Provide next-trip, next-stop, and route-stop query endpoints outside the
   router (`backend/api/urls.py:29`, `backend/api/urls.py:30`,
   `backend/api/urls.py:31`).
3. Represent stops and shapes as GeoJSON-compatible resources through
   `GeoFeatureModelSerializer` (`backend/api/serializers.py:112`,
   `backend/api/serializers.py:118`, `backend/api/serializers.py:154`,
   `backend/api/serializers.py:160`).
4. Serve Redoc against a repository-owned static OpenAPI YAML document
   (`backend/api/urls.py:33`, `backend/api/urls.py:34`,
   `backend/api/views.py:520`, `backend/api/views.py:523`).

The API does not acquire GTFS feeds, normalize Realtime messages, own transit
models, or own `InfoService`. Those responsibilities remain in `feed` and
`engine`; `api` imports their models and one feed query service
(`backend/api/views.py:3`, `backend/api/views.py:4`,
`backend/api/views.py:33`).

## Responsibilities and boundaries

### Responsibilities

- Register the Schedule and information-service resources that form the
  current router surface (`backend/api/urls.py:8`,
  `backend/api/urls.py:22`).
- Attach a model queryset, serializer, `DjangoFilterBackend`, and explicit
  filter fields to every defined ViewSet (`backend/api/views.py:55`,
  `backend/api/views.py:56`, `backend/api/views.py:57`,
  `backend/api/views.py:58`, `backend/api/views.py:513`,
  `backend/api/views.py:514`, `backend/api/views.py:515`,
  `backend/api/views.py:516`).
- Validate query parameters and serialize computed responses for the three
  APIViews (`backend/api/views.py:67`, `backend/api/views.py:102`,
  `backend/api/views.py:113`, `backend/api/views.py:164`,
  `backend/api/views.py:172`, `backend/api/views.py:234`).
- Construct the route-stop response as a GeoJSON `FeatureCollection`
  (`backend/api/views.py:199`, `backend/api/views.py:200`,
  `backend/api/views.py:207`, `backend/api/views.py:232`).
- Expose the DRF browsable-API login routes and the Redoc UI
  (`backend/api/urls.py:32`, `backend/api/urls.py:34`).

### Boundaries

- The app owns no database model or migration. `models.py` contains only the
  generated import and placeholder comment (`backend/api/models.py:1`,
  `backend/api/models.py:3`), and the repository-wide `migrations/` ignore
  rule is active (`.gitignore:87`).
- The router exposes Schedule-oriented resources plus `InfoService`; it does
  not register the five implemented Realtime ViewSets
  (`backend/api/urls.py:8`, `backend/api/urls.py:22`,
  `backend/api/views.py:428`, `backend/api/views.py:446`,
  `backend/api/views.py:459`, `backend/api/views.py:476`,
  `backend/api/views.py:490`).
- The app does not define a global or per-view authorization policy. The only
  active global DRF setting is token authentication
  (`backend/infobus/settings.py:168`, `backend/infobus/settings.py:172`),
  while the ViewSet permission declarations are comments
  (`backend/api/views.py:59`, `backend/api/views.py:252`,
  `backend/api/views.py:517`).
- OpenAPI generation is not connected to the URL configuration.
  `SpectacularAPIView` is imported, but the schema route calls the local
  `get_schema` file-serving view instead (`backend/api/urls.py:3`,
  `backend/api/urls.py:33`, `backend/api/views.py:520`).

## Domain model and persistence

**Status: implemented** as a stateless serialization app; model ownership is
**not found**. `backend/api/models.py` defines no model class
(`backend/api/models.py:1`, `backend/api/models.py:3`).

The serializers divide the delegated domain into three groups:

- Schedule catalog and service data from `feed`: `FeedPublisher`, `Agency`,
  `Stop`, `Route`, `Calendar`, `CalendarDate`, `Shape`, `GeoShape`, `Trip`,
  `StopTime`, `FeedInfo`, `FareAttribute`, and `FareRule`
  (`backend/api/serializers.py:9`, `backend/api/serializers.py:96`,
  `backend/api/serializers.py:104`, `backend/api/serializers.py:122`,
  `backend/api/serializers.py:130`, `backend/api/serializers.py:138`,
  `backend/api/serializers.py:146`, `backend/api/serializers.py:154`,
  `backend/api/serializers.py:164`, `backend/api/serializers.py:172`,
  `backend/api/serializers.py:180`, `backend/api/serializers.py:188`,
  `backend/api/serializers.py:196`).
- Realtime data from `feed`: `Alert`, `FeedMessage`, `TripUpdate`,
  `StopTimeUpdate`, and `VehiclePosition`
  (`backend/api/serializers.py:204`, `backend/api/serializers.py:212`,
  `backend/api/serializers.py:220`, `backend/api/serializers.py:228`,
  `backend/api/serializers.py:236`).
- Information-service data from `engine`: `InfoService`
  (`backend/api/serializers.py:1`, `backend/api/serializers.py:244`,
  `backend/api/serializers.py:246`).

All model serializers use `fields = "__all__"`. Selected foreign-key fields
are redeclared read-only, including `feed`, `provider`, `feed_message`, and
`trip_update` (`backend/api/serializers.py:97`,
`backend/api/serializers.py:101`, `backend/api/serializers.py:213`,
`backend/api/serializers.py:217`, `backend/api/serializers.py:221`,
`backend/api/serializers.py:229`, `backend/api/serializers.py:237`). The file
defines no custom `validate`, `create`, or `update` method; its last serializer
ends with the inherited `Meta` configuration
(`backend/api/serializers.py:244`, `backend/api/serializers.py:247`).

Migration ownership is **not found**: there is no `backend/api/migrations/`
tree tracked for this app, and the repository ignores directories named
`migrations/` (`.gitignore:87`). Because the app owns no models, API writes
target tables owned by `feed` or `engine`, not API-owned tables
(`backend/api/models.py:1`, `backend/api/models.py:3`,
`backend/api/views.py:3`, `backend/api/views.py:4`).

## Inputs

### Router inputs

The 15 registered `ModelViewSet` classes accept DRF collection and detail
requests. No class defines `http_method_names` or overrides the inherited
write handlers; therefore POST, PUT, PATCH, and DELETE remain enabled through
DRF's `ModelViewSet` behavior (`backend/api/views.py:50`,
`backend/api/views.py:243`, `backend/api/views.py:255`,
`backend/api/views.py:274`, `backend/api/views.py:292`,
`backend/api/views.py:312`, `backend/api/views.py:324`,
`backend/api/views.py:336`, `backend/api/views.py:348`,
`backend/api/views.py:360`, `backend/api/views.py:378`,
`backend/api/views.py:390`, `backend/api/views.py:402`,
`backend/api/views.py:415`, `backend/api/views.py:508`). The write-method
conclusion is a **framework inference** from those subclasses and the lack of
a local method restriction; it is not a separately declared API policy.

Query-string filtering is declared per ViewSet. Examples include publisher
`code` and `name`, stop identity and coordinate fields, trip identity and
service fields, and information-service `type` and `name`
(`backend/api/views.py:57`, `backend/api/views.py:58`,
`backend/api/views.py:262`, `backend/api/views.py:263`,
`backend/api/views.py:367`, `backend/api/views.py:368`,
`backend/api/views.py:515`, `backend/api/views.py:516`).

### Query-view inputs

- `GET /api/next-trips/` requires `stop_id`; `timestamp` is optional and
  `transit_system` defaults to `"default"`
  (`backend/api/urls.py:29`, `backend/api/views.py:67`,
  `backend/api/views.py:86`, `backend/api/views.py:94`).
- `GET /api/next-stops/` requires `trip_id`, `start_date`, and `start_time`
  (`backend/api/urls.py:30`, `backend/api/views.py:109`,
  `backend/api/views.py:113`).
- `GET /api/route-stops/` requires both `route_id` and `shape_id`
  (`backend/api/urls.py:31`, `backend/api/views.py:172`,
  `backend/api/views.py:175`, `backend/api/views.py:176`).

Token credentials are a recognized authentication input because
`TokenAuthentication` is configured globally
(`backend/infobus/settings.py:169`, `backend/infobus/settings.py:170`). They
are not required by an active permission class in repository configuration
(`backend/infobus/settings.py:168`, `backend/infobus/settings.py:172`).

## Outputs

### Router outputs

The standard resources use `HyperlinkedModelSerializer` and include all model
fields, subject to the explicitly read-only relationships
(`backend/api/serializers.py:9`, `backend/api/serializers.py:12`,
`backend/api/serializers.py:96`, `backend/api/serializers.py:101`,
`backend/api/serializers.py:244`, `backend/api/serializers.py:247`).

`GeoStopSerializer` emits `Stop` records with `stop_point` as the GeoJSON
geometry, while `GeoShapeSerializer` emits `GeoShape` records with `geometry`
as the GeoJSON geometry (`backend/api/serializers.py:112`,
`backend/api/serializers.py:114`, `backend/api/serializers.py:118`,
`backend/api/serializers.py:154`, `backend/api/serializers.py:156`,
`backend/api/serializers.py:160`).

### Query-view outputs

- `NextTripView` serializes `stop_id`, a timestamp, and nested next-arrival
  records (`backend/api/serializers.py:35`,
  `backend/api/serializers.py:38`, `backend/api/views.py:102`,
  `backend/api/views.py:103`).
- `NextStopView` serializes the trip identity and a nested stop sequence with
  coordinates and arrival/departure values
  (`backend/api/serializers.py:41`, `backend/api/serializers.py:55`,
  `backend/api/views.py:157`, `backend/api/views.py:166`).
- `RouteStopView` returns a GeoJSON-shaped `FeatureCollection` containing
  point geometry and route-stop properties
  (`backend/api/views.py:200`, `backend/api/views.py:207`,
  `backend/api/views.py:213`, `backend/api/views.py:232`,
  `backend/api/views.py:236`). The view does not explicitly select an
  `application/geo+json` media type; it returns serializer data through DRF's
  `Response` (`backend/api/views.py:234`, `backend/api/views.py:236`).

### Documentation output

`GET /api/docs/schema/` returns `backend/api/infobus.yml` as an attachment
named `infobus.yml` (`backend/api/urls.py:33`,
`backend/api/views.py:521`, `backend/api/views.py:522`,
`backend/api/views.py:523`). `GET /api/docs/` renders Redoc using that named
schema route (`backend/api/urls.py:34`).

## Internal and external dependencies

### Internal dependencies

- `engine.models.InfoService` is imported by both views and serializers
  (`backend/api/views.py:3`, `backend/api/serializers.py:1`).
- Views import the consumed Schedule and Realtime models explicitly from
  `feed.models` (`backend/api/views.py:4`, `backend/api/views.py:25`).
- `NextTripView` imports and calls `feed.services.queries.get_next_trips`
  (`backend/api/views.py:33`, `backend/api/views.py:95`).
- Serializers import `feed.models` with a wildcard rather than declaring the
  consumed model symbols individually (`backend/api/serializers.py:2`).

### External dependencies

- Django supplies URL routing, settings access, and `FileResponse`
  (`backend/api/urls.py:1`, `backend/api/views.py:1`,
  `backend/api/views.py:2`).
- Django REST framework supplies routers, ModelViewSets, APIViews, responses,
  status codes, and serializers (`backend/api/urls.py:2`,
  `backend/api/views.py:26`, `backend/api/views.py:27`,
  `backend/api/views.py:28`, `backend/api/views.py:30`,
  `backend/api/serializers.py:3`).
- `django-filter` supplies the per-ViewSet filtering backend
  (`backend/api/views.py:29`).
- `rest_framework_gis` supplies GeoJSON model serialization and geometry
  fields (`backend/api/serializers.py:4`).
- `drf-spectacular` supplies the Redoc view and an imported but unconnected
  schema view (`backend/api/urls.py:3`).
- `pytz` supplies timezone localization for the optional next-trip timestamp
  (`backend/api/views.py:32`, `backend/api/views.py:64`,
  `backend/api/views.py:90`).

## Entrypoints

The project mounts `api.urls` at `/api/`
(`backend/infobus/urls.py:32`). The router then exposes these registered
resources:

| URL | ViewSet | Delegated model |
| --- | --- | --- |
| `/api/info-services/` | `InfoServiceViewSet` | `engine.InfoService` (`backend/api/urls.py:8`, `backend/api/views.py:513`). |
| `/api/feed-publishers/` | `FeedPublisherViewSet` | `feed.FeedPublisher` (`backend/api/urls.py:9`, `backend/api/views.py:55`). |
| `/api/agencies/` | `AgencyViewSet` | `feed.Agency` (`backend/api/urls.py:10`, `backend/api/views.py:248`). |
| `/api/stops/` | `StopViewSet` | `feed.Stop` (`backend/api/urls.py:11`, `backend/api/views.py:260`). |
| `/api/geo-stops/` | `GeoStopViewSet` | `feed.Stop` as GeoJSON (`backend/api/urls.py:12`, `backend/api/views.py:279`). |
| `/api/shapes/` | `ShapeViewSet` | `feed.Shape` (`backend/api/urls.py:13`, `backend/api/views.py:341`). |
| `/api/geo-shapes/` | `GeoShapeViewSet` | `feed.GeoShape` (`backend/api/urls.py:14`, `backend/api/views.py:353`). |
| `/api/routes/` | `RouteViewSet` | `feed.Route` (`backend/api/urls.py:15`, `backend/api/views.py:297`). |
| `/api/calendars/` | `CalendarViewSet` | `feed.Calendar` (`backend/api/urls.py:16`, `backend/api/views.py:317`). |
| `/api/calendar-dates/` | `CalendarDateViewSet` | `feed.CalendarDate` (`backend/api/urls.py:17`, `backend/api/views.py:329`). |
| `/api/trips/` | `TripViewSet` | `feed.Trip` (`backend/api/urls.py:18`, `backend/api/views.py:365`). |
| `/api/stop-times/` | `StopTimeViewSet` | `feed.StopTime` (`backend/api/urls.py:19`, `backend/api/views.py:383`). |
| `/api/fare-attributes/` | `FareAttributeViewSet` | `feed.FareAttribute` (`backend/api/urls.py:20`, `backend/api/views.py:407`). |
| `/api/fare-rules/` | `FareRuleViewSet` | `feed.FareRule` (`backend/api/urls.py:21`, `backend/api/views.py:420`). |
| `/api/feed-info/` | `FeedInfoViewSet` | `feed.FeedInfo` (`backend/api/urls.py:22`, `backend/api/views.py:395`). |

Non-router entrypoints are:

- `/api/next-trips/`, `/api/next-stops/`, and `/api/route-stops/`
  (`backend/api/urls.py:29`, `backend/api/urls.py:30`,
  `backend/api/urls.py:31`).
- `/api/api-auth/` for DRF's browsable-API authentication URLs
  (`backend/api/urls.py:32`).
- `/api/docs/schema/` for the static YAML and `/api/docs/` for Redoc
  (`backend/api/urls.py:33`, `backend/api/urls.py:34`).

## Main flow

### Router flow

1. Django delegates an `/api/` request to `api.urls`
   (`backend/infobus/urls.py:32`).
2. `DefaultRouter` resolves one of the 15 registered ViewSets
   (`backend/api/urls.py:7`, `backend/api/urls.py:8`,
   `backend/api/urls.py:22`, `backend/api/urls.py:28`).
3. The ViewSet starts from its delegated model queryset and applies its local
   `DjangoFilterBackend` configuration
   (`backend/api/views.py:55`, `backend/api/views.py:57`,
   `backend/api/views.py:513`, `backend/api/views.py:515`).
4. The selected serializer reads or writes the delegated model. Model
   serializers include all model fields, with specific relationships marked
   read-only (`backend/api/serializers.py:12`,
   `backend/api/serializers.py:97`, `backend/api/serializers.py:101`).

Steps 3 and 4 use inherited DRF behavior; this is a **framework inference**
from the `ModelViewSet`, queryset, serializer, and filter declarations rather
than locally implemented request handlers (`backend/api/views.py:50`,
`backend/api/views.py:55`, `backend/api/views.py:56`,
`backend/api/views.py:57`).

### Next-trip flow

1. Validate `stop_id` against `feed.Stop`
   (`backend/api/views.py:67`, `backend/api/views.py:77`).
2. Parse and localize an optional timestamp and select the requested transit
   system (`backend/api/views.py:86`, `backend/api/views.py:90`,
   `backend/api/views.py:94`).
3. Call `feed.services.queries.get_next_trips` and serialize the result
   (`backend/api/views.py:95`, `backend/api/views.py:102`,
   `backend/api/views.py:103`).

### Next-stop flow

1. Require trip identity, start date, and start time
   (`backend/api/views.py:109`, `backend/api/views.py:113`).
2. Read the latest trip-update message and its ordered stop-time updates
   (`backend/api/views.py:124`, `backend/api/views.py:127`,
   `backend/api/views.py:133`).
3. Join those updates to stops in the current Schedule feed and serialize the
   sequence (`backend/api/views.py:137`, `backend/api/views.py:141`,
   `backend/api/views.py:145`, `backend/api/views.py:164`).

### Route-stop flow

1. Require `route_id` and `shape_id`, then select matching `RouteStop` rows
   (`backend/api/views.py:172`, `backend/api/views.py:178`).
2. Resolve each stop in the current feed
   (`backend/api/views.py:197`, `backend/api/views.py:204`).
3. Build, validate, and return a GeoJSON-shaped collection
   (`backend/api/views.py:200`, `backend/api/views.py:232`,
   `backend/api/views.py:234`, `backend/api/views.py:236`).

### Documentation flow

Redoc resolves the URL named `schema`, which is the local `get_schema` view;
that view opens and returns `backend/api/infobus.yml`
(`backend/api/urls.py:33`, `backend/api/urls.py:34`,
`backend/api/views.py:520`, `backend/api/views.py:523`). No dynamic
drf-spectacular generation participates in this flow.

## Configuration

### Django REST framework

**Status: partial.** The only configured DRF default is
`TokenAuthentication` (`backend/infobus/settings.py:168`,
`backend/infobus/settings.py:172`). The settings block defines no
`DEFAULT_PERMISSION_CLASSES`, `DEFAULT_PAGINATION_CLASS`,
`DEFAULT_FILTER_BACKENDS`, throttle classes/rates, or versioning class
(`backend/infobus/settings.py:168`, `backend/infobus/settings.py:172`). Filters
are instead attached to each ViewSet, for example
`backend/api/views.py:57` and `backend/api/views.py:515`.

**High-relevance limitation — framework inference:** because no
`DEFAULT_PERMISSION_CLASSES` is configured and no registered ViewSet has an
active `permission_classes`, DRF falls back to its default permission behavior
(`AllowAny`). Combined with unrestricted `ModelViewSet` subclasses, this means
the registered POST, PUT, PATCH, and DELETE actions do not require
authentication. The code facts are the closed settings block, the commented
permission declarations, and the mutable subclasses
(`backend/infobus/settings.py:168`, `backend/infobus/settings.py:172`,
`backend/api/views.py:50`, `backend/api/views.py:59`,
`backend/api/views.py:252`, `backend/api/views.py:271`,
`backend/api/views.py:289`, `backend/api/views.py:309`,
`backend/api/views.py:321`, `backend/api/views.py:333`,
`backend/api/views.py:345`, `backend/api/views.py:357`,
`backend/api/views.py:375`, `backend/api/views.py:387`,
`backend/api/views.py:399`, `backend/api/views.py:411`,
`backend/api/views.py:424`, `backend/api/views.py:517`); the `AllowAny`
consequence is explicitly a Django REST framework behavior inference.

### OpenAPI and Redoc

`SPECTACULAR_SETTINGS` configures only the title
(`backend/infobus/settings.py:174`, `backend/infobus/settings.py:176`). No
drf-spectacular version, tag, or exclusion setting is declared in that block.
The schema served to Redoc is instead the static YAML selected by
`get_schema` (`backend/api/views.py:520`, `backend/api/views.py:523`).

### API versioning

**Status: not found.** The project mounts the unversioned `/api/` prefix, and
the router prefixes contain no `v1` segment
(`backend/infobus/urls.py:32`, `backend/api/urls.py:8`,
`backend/api/urls.py:22`). The DRF settings block contains no
`DEFAULT_VERSIONING_CLASS` (`backend/infobus/settings.py:168`,
`backend/infobus/settings.py:172`). This documents repository evidence; it
does not assert that the lack of versioning is an intentional design choice.
The static document's `"1.0"` value is OpenAPI document metadata, not a route
version (`backend/api/infobus.yml:1`, `backend/api/infobus.yml:5`).

## Operation and observability

**Status: partial.** Normal operation is through the Django ASGI service at
the project `/api/` mount (`backend/infobus/urls.py:32`). The app exposes no
app-specific health or status endpoint; its explicit URL list consists of the
router, three query views, browsable authentication, static schema, and Redoc
(`backend/api/urls.py:28`, `backend/api/urls.py:34`).

The query views communicate failures through DRF responses, including bad
request, not found, no-content, and serializer-error branches
(`backend/api/views.py:68`, `backend/api/views.py:79`,
`backend/api/views.py:97`, `backend/api/views.py:114`,
`backend/api/views.py:182`, `backend/api/views.py:189`,
`backend/api/views.py:238`).

No module logger is configured. The only explicit diagnostic side effects in
the views are two `print` calls during next-stop and route-stop processing
(`backend/api/views.py:140`, `backend/api/views.py:206`). Request tracing,
metrics, structured API logs, throttling visibility, and write auditing are
**not found** in this app's source (`backend/api/views.py:1`,
`backend/api/views.py:35`, `backend/infobus/settings.py:168`,
`backend/infobus/settings.py:172`).

Useful manual entrypoints are:

```text
GET /api/
GET /api/next-trips/?stop_id=<stop-id>
GET /api/next-stops/?trip_id=<trip-id>&start_date=<date>&start_time=<time>
GET /api/route-stops/?route_id=<route-id>&shape_id=<shape-id>
GET /api/docs/
GET /api/docs/schema/
```

These paths derive from the root mount and app URL declarations
(`backend/infobus/urls.py:32`, `backend/api/urls.py:28`,
`backend/api/urls.py:29`, `backend/api/urls.py:30`,
`backend/api/urls.py:31`, `backend/api/urls.py:33`,
`backend/api/urls.py:34`).

## Testing

**Status: scaffolding.** `backend/api/tests.py` contains only the `TestCase`
import and the generated placeholder comment
(`backend/api/tests.py:1`, `backend/api/tests.py:3`). No implemented test
currently exercises router registration, write permissions, filters,
serializers, query validation, GeoJSON output, or schema/router consistency
(`backend/api/tests.py:1`, `backend/api/tests.py:3`).

The focused Django test command is:

```bash
cd backend
uv run python manage.py test api
```

At the documented HEAD, the module contains no test case for that command to
discover (`backend/api/tests.py:1`, `backend/api/tests.py:3`).

## Integration status

**Overall status: partial.** Schedule-oriented router resources, the
information-service resource, three query views, GeoJSON serializers, and
Redoc are connected, but Realtime ViewSets are not routed, authorization is
not enforced, and the static OpenAPI document is desynchronized
(`backend/api/urls.py:8`, `backend/api/urls.py:22`,
`backend/api/urls.py:29`, `backend/api/urls.py:34`,
`backend/api/views.py:428`, `backend/api/views.py:490`,
`backend/infobus/settings.py:168`, `backend/infobus/settings.py:172`,
`backend/api/infobus.yml:717`).

### Implemented

- Fifteen mutable router resources: 14 Schedule projections from `feed` and
  one `InfoService` projection from `engine`
  (`backend/api/urls.py:8`, `backend/api/urls.py:22`,
  `backend/api/views.py:3`, `backend/api/views.py:4`).
- Per-resource filtering through `DjangoFilterBackend`
  (`backend/api/views.py:29`, `backend/api/views.py:57`,
  `backend/api/views.py:515`).
- Next-trip, next-stop, and route-stop query views
  (`backend/api/urls.py:29`, `backend/api/urls.py:30`,
  `backend/api/urls.py:31`).
- GeoJSON serializers for stops and shapes
  (`backend/api/serializers.py:112`, `backend/api/serializers.py:118`,
  `backend/api/serializers.py:154`, `backend/api/serializers.py:160`).
- Static YAML delivery and a Redoc UI
  (`backend/api/urls.py:33`, `backend/api/urls.py:34`,
  `backend/api/views.py:520`, `backend/api/views.py:523`).

### Partial

- Five Realtime `ModelViewSet` implementations exist but are not registered:
  `ServiceAlertViewSet`, `FeedMessageViewSet`, `TripUpdateViewSet`,
  `StopTimeUpdateViewSet`, and `VehiclePositionViewSet`
  (`backend/api/views.py:428`, `backend/api/views.py:446`,
  `backend/api/views.py:459`, `backend/api/views.py:476`,
  `backend/api/views.py:490`). The router's registrations end with
  `FeedInfoViewSet` (`backend/api/urls.py:22`). Consequently, the router
  exposes Schedule resources, not Realtime resource ViewSets. The custom
  next-stop view may still read Realtime models internally
  (`backend/api/views.py:124`, `backend/api/views.py:133`).
- drf-spectacular is installed and Redoc is connected, but dynamic schema
  generation is not connected (`backend/infobus/settings.py:49`,
  `backend/api/urls.py:3`, `backend/api/urls.py:33`,
  `backend/api/urls.py:34`).
- Token authentication is configured, but no active permission policy makes
  it mandatory (`backend/infobus/settings.py:169`,
  `backend/infobus/settings.py:171`, `backend/api/views.py:59`).

### Broken

- The static OpenAPI document does not match the router. It declares
  `/info-service` while the router registers `info-services`
  (`backend/api/infobus.yml:717`, `backend/api/urls.py:8`), and it declares
  `/geoshapes` while the router registers `geo-shapes`
  (`backend/api/infobus.yml:354`, `backend/api/urls.py:14`).
- The YAML publishes Realtime endpoints such as `/vehicle-positions`,
  `/trip-updates`, and `/service-alerts`
  (`backend/api/infobus.yml:469`, `backend/api/infobus.yml:514`,
  `backend/api/infobus.yml:550`), but their ViewSets are not present in the
  router registrations (`backend/api/urls.py:8`,
  `backend/api/urls.py:22`).
- The YAML documents `feed-publishers` as GET-only, while the corresponding
  routed class is an unrestricted `ModelViewSet`
  (`backend/api/infobus.yml:18`, `backend/api/infobus.yml:19`,
  `backend/api/views.py:50`, `backend/api/views.py:59`).

### Scaffolding

- `models.py`, `admin.py`, and `tests.py` contain generated placeholders
  rather than API-owned models, Admin registrations, or tests
  (`backend/api/models.py:1`, `backend/api/models.py:3`,
  `backend/api/admin.py:1`, `backend/api/admin.py:3`,
  `backend/api/tests.py:1`, `backend/api/tests.py:3`).

### Not found

- An API-owned persistence model or tracked migration
  (`backend/api/models.py:1`, `backend/api/models.py:3`, `.gitignore:87`).
- Active global or per-ViewSet permission enforcement
  (`backend/infobus/settings.py:168`, `backend/infobus/settings.py:172`,
  `backend/api/views.py:59`, `backend/api/views.py:517`).
- Pagination, throttling, global filter backends, or route/header versioning
  in DRF configuration (`backend/infobus/settings.py:168`,
  `backend/infobus/settings.py:172`).
- Dynamic OpenAPI schema generation connected to a URL
  (`backend/api/urls.py:3`, `backend/api/urls.py:33`).
- Implemented API tests (`backend/api/tests.py:1`,
  `backend/api/tests.py:3`).

### Uncertain

- Whether deployed databases already contain all delegated `feed` and
  `engine` tables cannot be established from `api` source; this app only
  declares querysets against those models (`backend/api/views.py:3`,
  `backend/api/views.py:4`, `backend/api/views.py:55`,
  `backend/api/views.py:513`).
- Whether unauthenticated mutation is intentional or accidental is uncertain:
  the code combines mutable ViewSets with commented permission declarations,
  but contains no policy statement resolving that combination
  (`backend/api/views.py:50`, `backend/api/views.py:59`,
  `backend/api/views.py:508`, `backend/api/views.py:517`).
- Whether the unregistered Realtime resources are planned public endpoints or
  abandoned implementations is uncertain; the classes exist while router
  entries do not (`backend/api/views.py:428`,
  `backend/api/views.py:490`, `backend/api/urls.py:22`).

## Limitations and open decisions

### Known limitations

- **High relevance — unauthenticated mutation:** all 15 registered resources
  inherit mutable `ModelViewSet` actions, while no active global or local
  permission class requires authentication
  (`backend/api/views.py:50`, `backend/api/views.py:243`,
  `backend/api/views.py:255`, `backend/api/views.py:274`,
  `backend/api/views.py:292`, `backend/api/views.py:312`,
  `backend/api/views.py:324`, `backend/api/views.py:336`,
  `backend/api/views.py:348`, `backend/api/views.py:360`,
  `backend/api/views.py:378`, `backend/api/views.py:390`,
  `backend/api/views.py:402`, `backend/api/views.py:415`,
  `backend/api/views.py:508`, `backend/infobus/settings.py:168`,
  `backend/infobus/settings.py:172`). **Framework inference:** DRF's default
  permission behavior is `AllowAny`, so POST, PUT, PATCH, and DELETE are not
  authentication-gated in this configuration.
- **Static-schema drift:** Redoc receives a hand-maintained YAML whose resource
  names, methods, and Realtime paths disagree with the live router
  (`backend/api/views.py:520`, `backend/api/views.py:523`,
  `backend/api/infobus.yml:18`, `backend/api/infobus.yml:717`,
  `backend/api/urls.py:8`, `backend/api/urls.py:22`).
- **Realtime integration gap:** five complete Realtime ViewSets have no router
  registration (`backend/api/views.py:428`,
  `backend/api/views.py:446`, `backend/api/views.py:459`,
  `backend/api/views.py:476`, `backend/api/views.py:490`,
  `backend/api/urls.py:22`).
- **No route versioning:** neither the URL hierarchy nor DRF settings define a
  versioning mechanism (`backend/infobus/urls.py:32`,
  `backend/api/urls.py:8`, `backend/infobus/settings.py:168`,
  `backend/infobus/settings.py:172`).
- **No pagination or throttling:** neither is configured globally or on the
  ViewSets (`backend/infobus/settings.py:168`,
  `backend/infobus/settings.py:172`, `backend/api/views.py:50`,
  `backend/api/views.py:517`).
- **No regression coverage:** the test module remains scaffolding
  (`backend/api/tests.py:1`, `backend/api/tests.py:3`).
- **Limited observability:** query views use direct `print` calls and expose no
  app-specific metrics or status route (`backend/api/views.py:140`,
  `backend/api/views.py:206`, `backend/api/urls.py:28`,
  `backend/api/urls.py:34`).

### Open decisions

1. **Should the API be strictly read-only?** Decide whether all public router
   resources should use read-only ViewSets or explicitly restricted HTTP
   methods, or whether authenticated mutation is a supported contract. The
   current evidence does not resolve the decision: all 15 registrations point
   to mutable `ModelViewSet` subclasses, no `http_method_names` restriction is
   declared, and permission declarations are commented
   (`backend/api/urls.py:8`, `backend/api/urls.py:22`,
   `backend/api/views.py:50`, `backend/api/views.py:59`,
   `backend/api/views.py:508`, `backend/api/views.py:517`).
2. **Authorization policy:** if writes remain supported, define which clients
   may create, replace, patch, or delete delegated `feed` and `engine`
   resources. Token authentication is configured, but no permission class
   requires it (`backend/infobus/settings.py:169`,
   `backend/infobus/settings.py:171`, `backend/api/views.py:59`).
3. **Realtime publication:** decide whether the five implemented Realtime
   ViewSets should be registered, removed, or kept internal
   (`backend/api/views.py:428`, `backend/api/views.py:446`,
   `backend/api/views.py:459`, `backend/api/views.py:476`,
   `backend/api/views.py:490`, `backend/api/urls.py:22`).
4. **Schema authority:** decide whether the router and serializers or the
   static YAML are authoritative, and whether to connect
   `SpectacularAPIView`, generate a checked schema artifact, or maintain the
   YAML manually (`backend/api/urls.py:3`, `backend/api/urls.py:33`,
   `backend/api/views.py:520`, `backend/api/infobus.yml:717`).
5. **Versioning:** decide whether compatibility requires a URL, namespace,
   query-parameter, or media-type versioning policy. No mechanism is currently
   configured (`backend/infobus/urls.py:32`,
   `backend/infobus/settings.py:168`, `backend/infobus/settings.py:172`).
6. **Pagination and traffic policy:** decide whether collection endpoints need
   pagination, request throttling, maximum page sizes, or write-rate controls.
   None is currently configured (`backend/infobus/settings.py:168`,
   `backend/infobus/settings.py:172`).
