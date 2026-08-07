# Feed

The `feed` Django app is Infobús®'s durable GTFS data layer. It defines the
transit-system and publisher catalog, persists normalized GTFS Schedule and
Realtime data in PostgreSQL/PostGIS, provides read-side trip queries, and
exports selected Realtime history to partitioned Parquet files
(`backend/feed/models.py:33`, `backend/feed/services/schedule.py:29`,
`backend/feed/services/realtime.py:22`, `backend/feed/services/queries.py:22`,
`backend/feed/services/data.py:13`).

`feed` is a persistence and query boundary, not the acquisition orchestrator.
`engine.tasks` calls the Schedule service, passes decoded GTFS Realtime
protobuf messages to the Realtime services, and launches the Parquet exporters
(`backend/engine/tasks.py:41`, `backend/engine/tasks.py:79`,
`backend/engine/tasks.py:125`, `backend/engine/tasks.py:169`,
`backend/engine/tasks.py:192`, `backend/engine/tasks.py:198`).

## Purpose

The app has four connected purposes:

1. Model transit systems, feed publishers, GTFS Schedule tables, normalized
   GTFS Realtime entities, and auxiliary route/trip structures
   (`backend/feed/models.py:33`, `backend/feed/models.py:54`,
   `backend/feed/models.py:123`, `backend/feed/models.py:185`,
   `backend/feed/models.py:588`).
2. Import GTFS Schedule ZIP contents after detecting an ETag change
   (`backend/feed/services/schedule.py:54`,
   `backend/feed/services/schedule.py:57`,
   `backend/feed/services/schedule.py:61`).
3. Normalize decoded VehiclePositions, TripUpdates, and Alerts into relational
   records (`backend/feed/services/realtime.py:22`,
   `backend/feed/services/realtime.py:112`,
   `backend/feed/services/realtime.py:225`).
4. Serve next-trip queries and write hourly VehiclePosition and StopTimeUpdate
   history to Parquet (`backend/feed/services/queries.py:43`,
   `backend/feed/services/data.py:13`, `backend/feed/services/data.py:287`).

The app does not fetch or decode GTFS Realtime HTTP responses. Those operations
belong to `engine.tasks`, which creates protobuf `FeedMessage` objects, parses
the responses, and then calls `feed.services.realtime`
(`backend/engine/tasks.py:67`, `backend/engine/tasks.py:72`,
`backend/engine/tasks.py:79`, `backend/engine/tasks.py:113`,
`backend/engine/tasks.py:118`, `backend/engine/tasks.py:125`). Schedule HTTP
acquisition is different: it occurs inside `feed.services.schedule`
(`backend/feed/services/schedule.py:54`,
`backend/feed/services/schedule.py:61`).

## Responsibilities and limits

### Responsibilities

- Own `TransitSystem`, `FeedPublisher`, and `Feed`, including publisher URLs,
  timezone, activation state, and current-feed metadata
  (`backend/feed/models.py:33`, `backend/feed/models.py:54`,
  `backend/feed/models.py:90`, `backend/feed/models.py:95`,
  `backend/feed/models.py:100`, `backend/feed/models.py:105`,
  `backend/feed/models.py:110`, `backend/feed/models.py:114`,
  `backend/feed/models.py:123`).
- Persist the supported GTFS Schedule tables from ZIP members using ordered
  bulk inserts (`backend/feed/services/schedule.py:83`,
  `backend/feed/services/schedule.py:96`,
  `backend/feed/services/schedule.py:144`).
- Persist one metadata `FeedMessage` plus normalized entities for each
  Realtime service call (`backend/feed/services/realtime.py:24`,
  `backend/feed/services/realtime.py:43`,
  `backend/feed/services/realtime.py:114`,
  `backend/feed/services/realtime.py:134`,
  `backend/feed/services/realtime.py:178`,
  `backend/feed/services/realtime.py:227`,
  `backend/feed/services/realtime.py:255`).
- Resolve service calendars and produce the next-arrival payload consumed by
  callers (`backend/feed/services/queries.py:22`,
  `backend/feed/services/queries.py:43`,
  `backend/feed/services/queries.py:197`).
- Export VehiclePosition and StopTimeUpdate snapshots into hourly Hive-style
  Parquet partitions (`backend/feed/services/data.py:70`,
  `backend/feed/services/data.py:78`,
  `backend/feed/services/data.py:339`,
  `backend/feed/services/data.py:347`).
- Register the complete model catalog in Django Admin
  (`backend/feed/admin.py:44`, `backend/feed/admin.py:74`).

### Limits

- The app declares no Celery task. Scheduling and task fan-out are implemented
  by `engine.tasks`, which imports the feed services
  (`backend/engine/tasks.py:1`, `backend/engine/tasks.py:6`,
  `backend/engine/tasks.py:7`, `backend/engine/tasks.py:12`).
- The app has no REST API, serializer, ViewSet, or router of its own:
  `urls.py` contains only a placeholder and `views.py` contains only the
  default import and comment (`backend/feed/urls.py:1`,
  `backend/feed/views.py:1`, `backend/feed/views.py:3`).
- The app has no WebSocket consumer or event publisher. Realtime persistence
  imports only feed models, GTFS conversion helpers, timezone/GIS helpers, and
  Django transactions (`backend/feed/services/realtime.py:1`,
  `backend/feed/services/realtime.py:19`).
- Current run state, lifecycle policy, Redis writes, and update events are not
  feed responsibilities. `engine.tasks` calls `runs` separately after feed
  persistence (`backend/engine/tasks.py:16`, `backend/engine/tasks.py:20`,
  `backend/engine/tasks.py:79`, `backend/engine/tasks.py:80`,
  `backend/engine/tasks.py:125`, `backend/engine/tasks.py:126`).
- The external `gtfs` and `gtfs-io` clones are dependencies, not modules owned
  by this app (`backend/feed/models.py:6`,
  `backend/feed/services/schedule.py:20`).

### Source layout

- `models.py` defines shared, Schedule, auxiliary, and Realtime persistence
  models (`backend/feed/models.py:33`, `backend/feed/models.py:180`,
  `backend/feed/models.py:423`, `backend/feed/models.py:583`).
- `services/schedule.py` performs Schedule change detection, download, and
  import (`backend/feed/services/schedule.py:29`).
- `services/realtime.py` normalizes the three supported GTFS Realtime entity
  feeds (`backend/feed/services/realtime.py:22`,
  `backend/feed/services/realtime.py:112`,
  `backend/feed/services/realtime.py:225`).
- `services/queries.py` implements calendar and next-trip reads
  (`backend/feed/services/queries.py:22`,
  `backend/feed/services/queries.py:43`).
- `services/data.py` implements the two Parquet exporters
  (`backend/feed/services/data.py:13`, `backend/feed/services/data.py:287`).
- `admin.py` registers the model catalog; `apps.py` declares `FeedConfig`
  (`backend/feed/admin.py:44`, `backend/feed/admin.py:74`,
  `backend/feed/apps.py:4`, `backend/feed/apps.py:5`).
- `urls.py`, `views.py`, and `tests.py` are placeholders
  (`backend/feed/urls.py:1`, `backend/feed/views.py:3`,
  `backend/feed/tests.py:3`).

## Domain model and persistence

### Shared catalog and feed identity

`TransitSystem` groups publishers under a unique code and carries a name,
description, and activation flag (`backend/feed/models.py:33`,
`backend/feed/models.py:36`, `backend/feed/models.py:37`,
`backend/feed/models.py:43`, `backend/feed/models.py:46`).

`FeedPublisher` belongs to a `TransitSystem` through a cascading foreign key
and stores its code, identity/contact fields, Schedule and Realtime URLs,
timezone, and activation flag (`backend/feed/models.py:54`,
`backend/feed/models.py:60`, `backend/feed/models.py:63`,
`backend/feed/models.py:65`, `backend/feed/models.py:71`,
`backend/feed/models.py:81`, `backend/feed/models.py:90`,
`backend/feed/models.py:95`, `backend/feed/models.py:100`,
`backend/feed/models.py:105`, `backend/feed/models.py:110`,
`backend/feed/models.py:114`).

`Feed` represents one imported Schedule snapshot. Its primary key is
`feed_id`; it stores source publisher/system references, validity dates,
version, HTTP validators, current status, and retrieval time
(`backend/feed/models.py:123`, `backend/feed/models.py:128`,
`backend/feed/models.py:129`, `backend/feed/models.py:132`,
`backend/feed/models.py:135`, `backend/feed/models.py:141`). Both catalog
foreign keys use `SET_NULL` (`backend/feed/models.py:129`,
`backend/feed/models.py:132`).

### GTFS Schedule models

The concrete Schedule models inherit their GTFS fields from abstract
`gtfs-django` base classes imported by `feed.models`
(`backend/feed/models.py:6`, `backend/feed/models.py:18`). `feed` adds a
cascading foreign key to `Feed`, per-feed uniqueness constraints, and selected
local fields or behavior (`backend/feed/models.py:185`,
`backend/feed/models.py:190`, `backend/feed/models.py:202`,
`backend/feed/models.py:207`, `backend/feed/models.py:253`,
`backend/feed/models.py:260`).

- `Agency` inherits agency identity, name, contact, language, URL, and timezone
  fields (`backend/feed/models.py:185`, `backend/feed/models.py:190`).
- `Stop` inherits stop identity, names, coordinates, hierarchy, timezone, and
  accessibility fields; it adds `stop_point` and `stop_heading`
  (`backend/feed/models.py:202`, `backend/feed/models.py:207`,
  `backend/feed/models.py:209`, `backend/feed/models.py:213`). Its custom
  `save()` keeps scalar coordinates and `stop_point` aligned
  (`backend/feed/models.py:235`, `backend/feed/models.py:247`).
- `Route` inherits route identity, names, agency, mode, presentation, URL, and
  ordering fields (`backend/feed/models.py:253`,
  `backend/feed/models.py:260`).
- `Calendar` and `CalendarDate` inherit weekly service dates and date-specific
  exceptions; `CalendarDate` locally defines `holiday_name`
  (`backend/feed/models.py:271`, `backend/feed/models.py:276`,
  `backend/feed/models.py:289`, `backend/feed/models.py:294`,
  `backend/feed/models.py:295`).
- `Shape` inherits shape identifiers and ordered geographic points
  (`backend/feed/models.py:314`, `backend/feed/models.py:319`).
- `Trip` inherits route/service identity, direction, headsign, shape, block,
  and accessibility fields (`backend/feed/models.py:333`,
  `backend/feed/models.py:338`).
- `StopTime` inherits trip/stop identity, sequence, arrival/departure values,
  boarding behavior, distance, and timepoint fields
  (`backend/feed/models.py:349`, `backend/feed/models.py:354`).
- `FareAttribute` and `FareRule` inherit legacy fare fields and add the feed
  relationship (`backend/feed/models.py:368`,
  `backend/feed/models.py:373`, `backend/feed/models.py:386`,
  `backend/feed/models.py:391`). Their Schedule ingestion is **not found**:
  neither appears in the import map, which ends with `FeedInfo`
  (`backend/feed/services/schedule.py:83`,
  `backend/feed/services/schedule.py:92`).
- `FeedInfo` inherits publisher, language, validity, version, and contact
  metadata and adds the feed relationship (`backend/feed/models.py:412`,
  `backend/feed/models.py:417`).

### Auxiliary Schedule models

`GeoShape` stores one `LineString` plus descriptive metadata per feed/shape
(`backend/feed/models.py:428`, `backend/feed/models.py:433`,
`backend/feed/models.py:434`, `backend/feed/models.py:437`). `RouteStop`
links route, geometric shape, and stop identities and resolves its optional
foreign keys in `save()` (`backend/feed/models.py:460`,
`backend/feed/models.py:463`, `backend/feed/models.py:465`,
`backend/feed/models.py:469`, `backend/feed/models.py:474`,
`backend/feed/models.py:488`). `TripDuration` links route, point shape, and
calendar service and resolves those optional references in `save()`
(`backend/feed/models.py:498`, `backend/feed/models.py:501`,
`backend/feed/models.py:503`, `backend/feed/models.py:507`,
`backend/feed/models.py:511`, `backend/feed/models.py:534`). `TripTime` links
a trip and stop to one departure time and resolves its optional references in
`save()` (`backend/feed/models.py:548`, `backend/feed/models.py:554`,
`backend/feed/models.py:556`, `backend/feed/models.py:560`,
`backend/feed/models.py:574`).

Population of all four auxiliary models during Schedule import is **not
found** because the importer map contains only the nine concrete tables
(`backend/feed/services/schedule.py:83`,
`backend/feed/services/schedule.py:92`). `TripTime` population is explicitly
**scaffolding** through a TODO in its model docstring
(`backend/feed/models.py:550`).

### GTFS Realtime models

Realtime models are defined directly from `models.Model`; they do not inherit
from `gtfs-django` (`backend/feed/models.py:588`,
`backend/feed/models.py:635`, `backend/feed/models.py:666`,
`backend/feed/models.py:796`).

`FeedMessage` stores metadata, not the raw protobuf. It has a string primary
key, optional publisher with `SET_NULL`, entity type, automatic save time,
incrementality, and GTFS Realtime version (`backend/feed/models.py:147`,
`backend/feed/models.py:158`, `backend/feed/models.py:159`,
`backend/feed/models.py:162`, `backend/feed/models.py:163`,
`backend/feed/models.py:164`, `backend/feed/models.py:165`). The absence of a
binary or raw-payload field is visible in the complete field declaration
block (`backend/feed/models.py:158`, `backend/feed/models.py:165`).

`TripUpdate` stores normalized trip, vehicle, timestamp, and delay fields and
has a required cascading foreign key to `FeedMessage`
(`backend/feed/models.py:588`, `backend/feed/models.py:599`,
`backend/feed/models.py:602`, `backend/feed/models.py:623`).
`StopTimeUpdate` has a required cascading foreign key to `TripUpdate` and
stores stop identity, arrival/departure event values, and schedule relationship
(`backend/feed/models.py:635`, `backend/feed/models.py:643`,
`backend/feed/models.py:646`, `backend/feed/models.py:660`).

`VehiclePosition` stores normalized trip, vehicle, geographic position, stop,
timestamp, congestion, and occupancy values
(`backend/feed/models.py:666`, `backend/feed/models.py:682`,
`backend/feed/models.py:703`, `backend/feed/models.py:711`,
`backend/feed/models.py:719`, `backend/feed/models.py:736`,
`backend/feed/models.py:739`, `backend/feed/models.py:752`). Its optional
`feed_message` foreign key cascades on deletion
(`backend/feed/models.py:677`, `backend/feed/models.py:679`). Its custom
`save()` builds `position_point` from convertible longitude and latitude and
otherwise clears it (`backend/feed/models.py:780`,
`backend/feed/models.py:789`).

The Alert subtree is fully represented by nine models:

- `Alert` belongs optionally to `FeedMessage` with `CASCADE` and stores cause,
  effect, and severity (`backend/feed/models.py:796`,
  `backend/feed/models.py:798`, `backend/feed/models.py:801`,
  `backend/feed/models.py:819`, `backend/feed/models.py:836`).
- `TimeRange` and `EntitySelector` belong optionally to `Alert` with `CASCADE`
  (`backend/feed/models.py:848`, `backend/feed/models.py:849`,
  `backend/feed/models.py:860`, `backend/feed/models.py:861`).
- `TripDescriptor` belongs optionally to `EntitySelector`, and
  `ModifiedTripSelector` belongs optionally to `TripDescriptor`; both use
  `CASCADE` (`backend/feed/models.py:875`,
  `backend/feed/models.py:876`, `backend/feed/models.py:906`,
  `backend/feed/models.py:907`).
- `TranslatedString` belongs optionally to `Alert`, and `Translation` belongs
  optionally to `TranslatedString`; both use `CASCADE`
  (`backend/feed/models.py:922`, `backend/feed/models.py:923`,
  `backend/feed/models.py:941`, `backend/feed/models.py:942`).
- `TranslatedImage` belongs optionally to `Alert`, and `LocalizedImage`
  belongs optionally to `TranslatedImage`; both use `CASCADE`
  (`backend/feed/models.py:955`, `backend/feed/models.py:956`,
  `backend/feed/models.py:962`, `backend/feed/models.py:963`).

Only `FeedMessage`, `TripUpdate`, `StopTimeUpdate`, and `VehiclePosition`
define their own `__str__()` methods (`backend/feed/models.py:176`,
`backend/feed/models.py:631`, `backend/feed/models.py:662`,
`backend/feed/models.py:792`). Of the Realtime models, only
`VehiclePosition` defines a custom `save()` (`backend/feed/models.py:780`).

### Migration state

The working tree contains a generated physical
`backend/feed/migrations/0001_initial.py` whose migration class begins at
`backend/feed/migrations/0001_initial.py:9`, but `git ls-files
backend/feed/migrations` returns no versioned migration. The repository-wide
`migrations/` ignore rule is `.gitignore:87`. Clean-clone schema creation is
therefore **broken** for this app unless migration policy is corrected.

## Inputs

### Schedule inputs

`save_schedule_to_database(feed_publisher, result)` accepts a publisher model
and a mutable result mapping (`backend/feed/services/schedule.py:29`). It reads
the publisher's `schedule_url` (`backend/feed/services/schedule.py:33`), makes
an HTTP `HEAD` request (`backend/feed/services/schedule.py:54`), and downloads
the ZIP with `GET` when the ETag differs (`backend/feed/services/schedule.py:57`,
`backend/feed/services/schedule.py:61`).

The ZIP members recognized by the importer are `agency.txt`, `stops.txt`,
`shapes.txt`, `calendar.txt`, `calendar_dates.txt`, `routes.txt`, `trips.txt`,
`stop_times.txt`, and `feed_info.txt` through the ordered map and filename
construction (`backend/feed/services/schedule.py:83`,
`backend/feed/services/schedule.py:93`,
`backend/feed/services/schedule.py:97`). A table is imported only when that
member exists (`backend/feed/services/schedule.py:98`).

### Realtime inputs

The three Realtime functions accept a `FeedPublisher` plus an already decoded
protobuf feed object; their signatures carry no type annotations
(`backend/feed/services/realtime.py:22`,
`backend/feed/services/realtime.py:112`,
`backend/feed/services/realtime.py:225`). `engine.tasks` constructs and parses
those protobuf objects before calling the functions
(`backend/engine/tasks.py:67`, `backend/engine/tasks.py:72`,
`backend/engine/tasks.py:113`, `backend/engine/tasks.py:118`,
`backend/engine/tasks.py:159`, `backend/engine/tasks.py:162`).

### Query inputs

`get_calendar(date, current_feed)` accepts a date-like object supporting
`strftime()` and a current `Feed`; the signature has no annotations
(`backend/feed/services/queries.py:22`,
`backend/feed/services/queries.py:32`). `get_next_trips(transit_system,
stop_id, timestamp=None)` accepts a transit-system value, stop identifier, and
optional timestamp without annotations (`backend/feed/services/queries.py:43`).

### Export inputs

Both exporters accept `use_current_hour=False` without annotations
(`backend/feed/services/data.py:13`, `backend/feed/services/data.py:287`). A
string input is normalized against `1`, `true`, `yes`, `y`, and `on`
(`backend/feed/services/data.py:22`, `backend/feed/services/data.py:29`,
`backend/feed/services/data.py:296`, `backend/feed/services/data.py:303`).

## Outputs

### PostgreSQL/PostGIS

Schedule import creates a `Feed`, conditionally updates feed validity/version
from `feed_info.txt`, and bulk-creates supported table rows
(`backend/feed/services/schedule.py:75`,
`backend/feed/services/schedule.py:108`,
`backend/feed/services/schedule.py:131`,
`backend/feed/services/schedule.py:144`). Vehicle persistence creates a
`FeedMessage` and bulk-creates `VehiclePosition` rows
(`backend/feed/services/realtime.py:24`,
`backend/feed/services/realtime.py:35`,
`backend/feed/services/realtime.py:106`). Trip-update persistence creates a
`FeedMessage`, `TripUpdate` rows, and child `StopTimeUpdate` rows
(`backend/feed/services/realtime.py:114`,
`backend/feed/services/realtime.py:125`,
`backend/feed/services/realtime.py:167`,
`backend/feed/services/realtime.py:209`). Alert persistence creates a
`FeedMessage` plus the available normalized Alert subtree
(`backend/feed/services/realtime.py:227`,
`backend/feed/services/realtime.py:238`,
`backend/feed/services/realtime.py:255`,
`backend/feed/services/realtime.py:433`).

### Query results

`get_calendar()` returns one service ID or `None`
(`backend/feed/services/queries.py:29`,
`backend/feed/services/queries.py:40`). `get_next_trips()` returns `None` when
no service is found, otherwise a mapping containing `stop_id`, `timestamp`,
and `next_arrivals` (`backend/feed/services/queries.py:75`,
`backend/feed/services/queries.py:77`,
`backend/feed/services/queries.py:197`,
`backend/feed/services/queries.py:203`).

### Parquet files

VehiclePosition history is written below
`/app/data/vehicle_positions/date=YYYY-MM-DD/hour=HH/` and StopTimeUpdate
history below `/app/data/stop_time_updates/date=YYYY-MM-DD/hour=HH/`; each file
is named `part-<uuid7>.parquet` (`backend/feed/services/data.py:70`,
`backend/feed/services/data.py:78`, `backend/feed/services/data.py:339`,
`backend/feed/services/data.py:347`). Both writers are created lazily and use
Zstandard compression (`backend/feed/services/data.py:191`,
`backend/feed/services/data.py:199`, `backend/feed/services/data.py:203`,
`backend/feed/services/data.py:394`, `backend/feed/services/data.py:402`,
`backend/feed/services/data.py:406`).

## Internal and external dependencies

### Internal dependencies

- `engine.tasks` invokes all write and export services; it also forwards
  VehiclePositions and TripUpdates independently to `runs`
  (`backend/engine/tasks.py:79`, `backend/engine/tasks.py:80`,
  `backend/engine/tasks.py:125`, `backend/engine/tasks.py:126`,
  `backend/engine/tasks.py:169`, `backend/engine/tasks.py:192`,
  `backend/engine/tasks.py:198`).
- `runs` consumes decoded Realtime messages through calls made by `engine`, not
  through imports in `feed.services.realtime`
  (`backend/engine/tasks.py:16`, `backend/engine/tasks.py:20`,
  `backend/feed/services/realtime.py:1`,
  `backend/feed/services/realtime.py:19`).
- The project installs `feed.apps.FeedConfig` and uses
  `America/Costa_Rica` as its configured timezone
  (`backend/infobus/settings.py:40`, `backend/infobus/settings.py:195`).

### External dependencies

- Django ORM, GeoDjango, and database transactions back the models and atomic
  Realtime child writes (`backend/feed/models.py:2`,
  `backend/feed/models.py:4`, `backend/feed/services/realtime.py:18`,
  `backend/feed/services/realtime.py:19`).
- `requests`, `zipfile`, pandas, and timezone/date conversion utilities support
  Schedule acquisition and parsing (`backend/feed/services/schedule.py:14`,
  `backend/feed/services/schedule.py:15`,
  `backend/feed/services/schedule.py:17`,
  `backend/feed/services/schedule.py:19`,
  `backend/feed/services/schedule.py:20`).
- GTFS Realtime protobuf objects are constructed by `engine` through Google's
  generated bindings (`backend/engine/tasks.py:4`,
  `backend/engine/tasks.py:67`).
- Shapely supports current-position projection in `get_next_trips()`
  (`backend/feed/services/queries.py:19`,
  `backend/feed/services/queries.py:128`,
  `backend/feed/services/queries.py:131`).
- PyArrow writes Parquet data, while `pathlib`, UUIDv7, and JSON support output
  layout and GeoParquet metadata (`backend/feed/services/data.py:5`,
  `backend/feed/services/data.py:6`, `backend/feed/services/data.py:7`,
  `backend/feed/services/data.py:8`, `backend/feed/services/data.py:9`).

`gtfs` (`gtfs-django`) and `gtfs-io` are external clones, not feed-owned code.
The entrypoint clones them dynamically without pinning a commit
(`backend/docker-entrypoint.sh:32`). For reproducibility, the local
`gtfs-django` clone observed during this documentation verification was at
`13543fe81cc8ae282926143b79e238c005e89392`; deployments are **not verifiable**
as using that same revision because the entrypoint does not fix it
(`backend/docker-entrypoint.sh:32`).

## Entrypoints

### Service entrypoints

- Schedule persistence: `save_schedule_to_database(feed_publisher, result)`
  (`backend/feed/services/schedule.py:29`).
- Vehicle persistence:
  `save_vehicle_positions_to_database(feed_publisher, vehicle_positions)`
  (`backend/feed/services/realtime.py:22`).
- Trip-update persistence:
  `save_trip_updates_to_database(feed_publisher, trip_updates)`
  (`backend/feed/services/realtime.py:112`).
- Alert persistence: `save_alerts_to_database(feed_publisher, alerts)`
  (`backend/feed/services/realtime.py:225`).
- Read services: `get_calendar(date, current_feed)` and
  `get_next_trips(transit_system, stop_id, timestamp=None)`
  (`backend/feed/services/queries.py:22`,
  `backend/feed/services/queries.py:43`).
- Historical exports: `vehicle_positions_to_parquet(use_current_hour=False)`
  and `stop_time_updates_to_parquet(use_current_hour=False)`
  (`backend/feed/services/data.py:13`, `backend/feed/services/data.py:287`).

### Connected callers

`engine.tasks` calls Schedule persistence at
`backend/engine/tasks.py:41`, VehiclePosition persistence at
`backend/engine/tasks.py:79`, TripUpdate persistence at
`backend/engine/tasks.py:125`, Alert persistence at
`backend/engine/tasks.py:169`, and the two exporters at
`backend/engine/tasks.py:192` and `backend/engine/tasks.py:198`.

### Django Admin

All feed models are registered in the contiguous registration block
`backend/feed/admin.py:44` through `backend/feed/admin.py:74`. GIS-aware admin
is used for `Stop` through `StopAdmin`, for `GeoShape` directly, and for
`VehiclePosition` directly (`backend/feed/admin.py:40`,
`backend/feed/admin.py:48`, `backend/feed/admin.py:53`,
`backend/feed/admin.py:65`).

### Entrypoints not present

There is no feed-owned Celery task, HTTP route, DRF ViewSet, WebSocket
consumer, management command, signal, or startup hook in the reviewed app.
The app config only sets its name (`backend/feed/apps.py:4`,
`backend/feed/apps.py:5`), while its URL and view modules remain placeholders
(`backend/feed/urls.py:1`, `backend/feed/views.py:3`). The absence of an
app-owned Celery task is also reflected by the fact that the connected task
definitions are in `engine.tasks` (`backend/engine/tasks.py:29`,
`backend/engine/tasks.py:46`, `backend/engine/tasks.py:93`,
`backend/engine/tasks.py:139`).

## Main flow

```mermaid
flowchart TD
    E[engine.tasks] -->|publisher + result| S[Schedule service]
    S --> Z[GTFS Schedule ZIP]
    S --> SD[(Schedule models)]

    E -->|decoded protobuf| R[Realtime services]
    R --> FM[(FeedMessage metadata)]
    R --> VP[(VehiclePosition)]
    R --> TU[(TripUpdate / StopTimeUpdate)]
    R --> A[(Alert subtree)]

    E --> P[Parquet exporters]
    VP --> P
    TU --> P
    P --> L[/app/data lake]

    Q[Query callers] --> G[get_next_trips]
    SD --> G
    FM --> G
    VP --> G
    TU --> G
```

The three branches in the diagram correspond to the Schedule call, Realtime
calls, and export calls in `engine.tasks` (`backend/engine/tasks.py:41`,
`backend/engine/tasks.py:79`, `backend/engine/tasks.py:125`,
`backend/engine/tasks.py:169`, `backend/engine/tasks.py:192`,
`backend/engine/tasks.py:198`).

### Schedule import

1. Resolve the current feed for the publisher and copy its ETag
   (`backend/feed/services/schedule.py:40`,
   `backend/feed/services/schedule.py:47`).
2. Issue `HEAD`, read `ETag` by direct header indexing, and compare it with the
   current value (`backend/feed/services/schedule.py:54`,
   `backend/feed/services/schedule.py:55`,
   `backend/feed/services/schedule.py:57`).
3. On change, issue `GET`, open the response as a ZIP, and read
   `Last-Modified` by direct indexing (`backend/feed/services/schedule.py:61`,
   `backend/feed/services/schedule.py:62`,
   `backend/feed/services/schedule.py:64`).
4. Mark the previous feed non-current before creating the replacement
   (`backend/feed/services/schedule.py:72`,
   `backend/feed/services/schedule.py:75`). The replacement receives its
   publisher but not `transit_system`, even though that field is nullable
   (`backend/feed/services/schedule.py:80`,
   `backend/feed/models.py:132`).
5. Iterate the ordered Agency, Stop, Shape, Calendar, CalendarDate, Route, Trip,
   StopTime, and FeedInfo map (`backend/feed/services/schedule.py:83`,
   `backend/feed/services/schedule.py:92`).
6. When a member exists, parse it as strings, normalize values, attach the new
   feed, and bulk-create rows (`backend/feed/services/schedule.py:98`,
   `backend/feed/services/schedule.py:101`,
   `backend/feed/services/schedule.py:133`,
   `backend/feed/services/schedule.py:134`,
   `backend/feed/services/schedule.py:144`).
7. Report success only after the loop completes
   (`backend/feed/services/schedule.py:147`,
   `backend/feed/services/schedule.py:148`).

No `transaction.atomic()` wraps this sequence; the function begins at
`backend/feed/services/schedule.py:29`, performs the cutover at
`backend/feed/services/schedule.py:72`, and bulk-inserts later at
`backend/feed/services/schedule.py:144`.

The same bulk path also bypasses `Stop.save()`. The importer adds the feed and
bulk-creates model instances without assigning `stop_point`, while the method
that derives `stop_point` from longitude/latitude is the custom `save()`
(`backend/feed/services/schedule.py:133`,
`backend/feed/services/schedule.py:134`,
`backend/feed/services/schedule.py:144`,
`backend/feed/models.py:235`, `backend/feed/models.py:247`).

### VehiclePosition persistence

The service creates and saves a `FeedMessage`, maps each vehicle entity into a
`VehiclePosition`, constructs `position_point` directly when both coordinates
exist, and performs one bulk insert (`backend/feed/services/realtime.py:24`,
`backend/feed/services/realtime.py:35`,
`backend/feed/services/realtime.py:43`,
`backend/feed/services/realtime.py:71`,
`backend/feed/services/realtime.py:106`). Because `bulk_create()` does not call
the model's custom `save()`, the direct point construction at lines 71–73 is
the persistence path used by this service (`backend/feed/services/realtime.py:71`,
`backend/feed/services/realtime.py:73`,
`backend/feed/services/realtime.py:106`,
`backend/feed/models.py:780`).

### TripUpdate persistence

The service saves `FeedMessage` before entering its transaction, accumulates
`TripUpdate` inputs, and then atomically bulk-creates parent rows followed by
their `StopTimeUpdate` children (`backend/feed/services/realtime.py:114`,
`backend/feed/services/realtime.py:125`,
`backend/feed/services/realtime.py:128`,
`backend/feed/services/realtime.py:166`,
`backend/feed/services/realtime.py:167`,
`backend/feed/services/realtime.py:178`,
`backend/feed/services/realtime.py:209`). A child-write failure can roll back
the TripUpdate/StopTimeUpdate transaction while leaving the earlier
`FeedMessage` row persisted (`backend/feed/services/realtime.py:125`,
`backend/feed/services/realtime.py:166`).

### Alert persistence

The service saves `FeedMessage`, computes already-known entity IDs, skips
duplicates, and uses one transaction per new alert
(`backend/feed/services/realtime.py:227`,
`backend/feed/services/realtime.py:238`,
`backend/feed/services/realtime.py:243`,
`backend/feed/services/realtime.py:250`,
`backend/feed/services/realtime.py:254`). It conditionally creates:

- `TimeRange` only when active periods exist
  (`backend/feed/services/realtime.py:266`,
  `backend/feed/services/realtime.py:277`).
- `EntitySelector`, `TripDescriptor`, and `ModifiedTripSelector` when the
  corresponding nested messages exist (`backend/feed/services/realtime.py:283`,
  `backend/feed/services/realtime.py:299`,
  `backend/feed/services/realtime.py:307`,
  `backend/feed/services/realtime.py:342`,
  `backend/feed/services/realtime.py:367`,
  `backend/feed/services/realtime.py:369`).
- `TranslatedString` and `Translation` only for fields containing translations
  (`backend/feed/services/realtime.py:391`,
  `backend/feed/services/realtime.py:394`,
  `backend/feed/services/realtime.py:395`).
- `TranslatedImage` and `LocalizedImage` only when localized images exist
  (`backend/feed/services/realtime.py:409`,
  `backend/feed/services/realtime.py:417`,
  `backend/feed/services/realtime.py:418`,
  `backend/feed/services/realtime.py:421`).

`has_optional_field()` safely checks protobuf descriptor membership and catches
`ValueError`, but it is used only for the Alert `image` field
(`backend/feed/services/realtime.py:215`,
`backend/feed/services/realtime.py:217`,
`backend/feed/services/realtime.py:220`,
`backend/feed/services/realtime.py:221`,
`backend/feed/services/realtime.py:413`). Other mappings call `HasField()`
directly (`backend/feed/services/realtime.py:46`,
`backend/feed/services/realtime.py:137`,
`backend/feed/services/realtime.py:181`).

### Query flow

`get_calendar()` first looks for an added-service `CalendarDate` exception and
otherwise selects the first calendar row active for the weekday
(`backend/feed/services/queries.py:24`,
`backend/feed/services/queries.py:25`,
`backend/feed/services/queries.py:32`,
`backend/feed/services/queries.py:34`). `get_next_trips()` selects the latest
current feed scoped by transit system, resolves a publisher/agency timezone,
normalizes the timestamp, and calls `get_calendar()`
(`backend/feed/services/queries.py:52`,
`backend/feed/services/queries.py:53`,
`backend/feed/services/queries.py:59`,
`backend/feed/services/queries.py:66`,
`backend/feed/services/queries.py:68`,
`backend/feed/services/queries.py:75`).

The query combines Realtime stop updates from the latest `trip_update`
`FeedMessage` with scheduled `StopTime` rows in the next five hours, then sorts
the combined arrivals (`backend/feed/services/queries.py:85`,
`backend/feed/services/queries.py:95`,
`backend/feed/services/queries.py:160`,
`backend/feed/services/queries.py:164`,
`backend/feed/services/queries.py:195`). Important scoping limitations are
listed below.

### Parquet flow

By default each exporter selects the last complete local hour; debug mode
selects the current hour (`backend/feed/services/data.py:31`,
`backend/feed/services/data.py:36`, `backend/feed/services/data.py:305`,
`backend/feed/services/data.py:310`). VehiclePosition uses
`timestamp >= window_start` and `< window_end`
(`backend/feed/services/data.py:211`,
`backend/feed/services/data.py:214`). StopTimeUpdate uses the same semi-open
window against the parent `TripUpdate.timestamp`, not arrival, departure, or
`FeedMessage.timestamp` (`backend/feed/services/data.py:414`,
`backend/feed/services/data.py:417`). Records are streamed in chunks of 5,000,
flushed into a lazily opened writer, and the writer is closed in `finally`
(`backend/feed/services/data.py:68`, `backend/feed/services/data.py:191`,
`backend/feed/services/data.py:262`, `backend/feed/services/data.py:274`,
`backend/feed/services/data.py:337`, `backend/feed/services/data.py:394`,
`backend/feed/services/data.py:499`, `backend/feed/services/data.py:511`).

## Configuration

### Publisher configuration

Feed endpoints and source timezone are database fields, not feed-specific
environment variables: `FeedPublisher` declares `schedule_url`,
`trip_updates_url`, `vehicle_positions_url`, `alerts_url`, and `timezone`
(`backend/feed/models.py:90`, `backend/feed/models.py:95`,
`backend/feed/models.py:100`, `backend/feed/models.py:105`,
`backend/feed/models.py:110`). `is_active` controls publisher selection in
`engine.tasks` (`backend/feed/models.py:114`,
`backend/engine/tasks.py:31`, `backend/engine/tasks.py:57`).

### Timezone and export windows

The project timezone is `America/Costa_Rica`
(`backend/infobus/settings.py:195`). Exporters use `settings.TIME_ZONE` to
construct local windows and timestamp schemas
(`backend/feed/services/data.py:19`, `backend/feed/services/data.py:20`,
`backend/feed/services/data.py:167`, `backend/feed/services/data.py:293`,
`backend/feed/services/data.py:294`, `backend/feed/services/data.py:355`).

### Data-lake mount

The output root is hard-coded as `/app/data`
(`backend/feed/services/data.py:71`, `backend/feed/services/data.py:340`). The
development Compose file mounts `lake_data` there for orchestrator, engine,
and scheduler services (`compose.dev.yml:19`, `compose.dev.yml:39`,
`compose.dev.yml:61`); production declares the corresponding mounts at
`compose.prod.yml:40`, `compose.prod.yml:76`, and `compose.prod.yml:103`.

### App and migration configuration

The project installs `feed.apps.FeedConfig`
(`backend/infobus/settings.py:40`). Migration directories are ignored by the
repository rule at `.gitignore:87`, and the physical feed initial migration
is not tracked in `HEAD`; migration handling is therefore **broken** for clean
clones (`backend/feed/migrations/0001_initial.py:9`, `.gitignore:87`).

## Operation and observability

### Logging and return values

Schedule persistence configures root logging at module import and emits
informational messages for acquisition, table completion, and final status
(`backend/feed/services/schedule.py:22`,
`backend/feed/services/schedule.py:26`,
`backend/feed/services/schedule.py:58`,
`backend/feed/services/schedule.py:145`,
`backend/feed/services/schedule.py:147`,
`backend/feed/services/schedule.py:151`). Realtime persistence contains no
logging setup or logger import in its complete import block
(`backend/feed/services/realtime.py:1`,
`backend/feed/services/realtime.py:19`).

The Parquet functions report completion, selected window, mode, output path,
and row count through returned strings; a no-row run returns a skipped result
(`backend/feed/services/data.py:268`,
`backend/feed/services/data.py:283`,
`backend/feed/services/data.py:505`,
`backend/feed/services/data.py:520`). `engine.tasks` returns those exporter
results to Celery callers (`backend/engine/tasks.py:192`,
`backend/engine/tasks.py:198`).

### Failure behavior

Schedule HTTP calls have neither a timeout argument nor `raise_for_status()`
(`backend/feed/services/schedule.py:54`,
`backend/feed/services/schedule.py:61`). Required `ETag` and `Last-Modified`
headers are indexed directly (`backend/feed/services/schedule.py:55`,
`backend/feed/services/schedule.py:64`). Schedule cutover is not atomic and
deactivates the previous feed before bulk insertion completes
(`backend/feed/services/schedule.py:72`,
`backend/feed/services/schedule.py:74`,
`backend/feed/services/schedule.py:144`).

TripUpdate child persistence and each Alert subtree use transactions, but
their `FeedMessage` records are saved first and outside those transactions
(`backend/feed/services/realtime.py:125`,
`backend/feed/services/realtime.py:166`,
`backend/feed/services/realtime.py:238`,
`backend/feed/services/realtime.py:254`). VehiclePosition persistence has no
transaction around its `FeedMessage` and bulk insert
(`backend/feed/services/realtime.py:35`,
`backend/feed/services/realtime.py:106`).

### Manual checks

Use Django Admin to inspect publisher configuration and stored rows; all models
are registered in `backend/feed/admin.py:44` through
`backend/feed/admin.py:74`. Use the exporter return strings and the mounted
`/app/data` partitions to verify historical output
(`backend/feed/services/data.py:70`, `backend/feed/services/data.py:78`,
`backend/feed/services/data.py:278`,
`backend/feed/services/data.py:339`,
`backend/feed/services/data.py:347`,
`backend/feed/services/data.py:515`). There is no feed-owned health endpoint or
status page because the URL and view modules are placeholders
(`backend/feed/urls.py:1`, `backend/feed/views.py:3`).

No retention, cleanup, purge, or snapshot deletion implementation was found in
`backend/feed/`. The only TTL reference is a TODO in the query service
(`backend/feed/services/queries.py:90`), while Parquet filenames are newly
generated UUIDv7 values (`backend/feed/services/data.py:78`,
`backend/feed/services/data.py:347`).

## Testing

**Status: scaffolding.** `backend/feed/tests.py` contains only the `TestCase`
import and the default placeholder comment (`backend/feed/tests.py:1`,
`backend/feed/tests.py:3`). No feed tests exercise Schedule change detection,
transaction boundaries, malformed ZIP/header handling, model constraints,
Realtime normalization, duplicate alerts, queries, Parquet schemas/windows,
Admin registration, or migration reproducibility (`backend/feed/tests.py:1`,
`backend/feed/tests.py:3`).

The app's focused test command is:

```bash
cd backend
uv run python manage.py test feed
```

At the documented HEAD, that command discovers no implemented feed tests
because the test module is only scaffolding (`backend/feed/tests.py:1`,
`backend/feed/tests.py:3`).

## Integration status

**Overall status: partial.** The core Schedule, Realtime, query, Admin, and
Parquet paths are present, but schema reproducibility, Schedule atomicity,
query correctness, retention, and several model/normalization contracts remain
incomplete or broken (`backend/feed/services/schedule.py:72`,
`backend/feed/services/schedule.py:144`,
`backend/feed/services/queries.py:85`,
`backend/feed/services/queries.py:165`,
`backend/feed/models.py:682`,
`backend/feed/services/realtime.py:46`, `.gitignore:87`).

### Implemented

- Ordered import of Agency, Stop, Shape, Calendar, CalendarDate, Route, Trip,
  StopTime, and FeedInfo (`backend/feed/services/schedule.py:83`,
  `backend/feed/services/schedule.py:92`,
  `backend/feed/services/schedule.py:144`).
- Normalized persistence for VehiclePosition, TripUpdate/StopTimeUpdate, and
  the complete conditional Alert subtree
  (`backend/feed/services/realtime.py:106`,
  `backend/feed/services/realtime.py:167`,
  `backend/feed/services/realtime.py:209`,
  `backend/feed/services/realtime.py:255`,
  `backend/feed/services/realtime.py:433`).
- Transit-system-scoped selection of the current Schedule feed
  (`backend/feed/services/queries.py:52`,
  `backend/feed/services/queries.py:53`).
- Semi-open hourly VehiclePosition and StopTimeUpdate export windows and
  partitioned Zstandard Parquet output
  (`backend/feed/services/data.py:211`,
  `backend/feed/services/data.py:214`,
  `backend/feed/services/data.py:414`,
  `backend/feed/services/data.py:417`,
  `backend/feed/services/data.py:200`,
  `backend/feed/services/data.py:203`).
- Full Django Admin registration
  (`backend/feed/admin.py:44`, `backend/feed/admin.py:74`).

### Partial

- Schedule replacement has no encompassing transaction and changes current
  state before the replacement is fully imported
  (`backend/feed/services/schedule.py:72`,
  `backend/feed/services/schedule.py:144`).
- Schedule `Stop` import uses `bulk_create()` and therefore bypasses the custom
  `Stop.save()` that derives `stop_point`; the importer does not otherwise set
  that GIS field (`backend/feed/services/schedule.py:133`,
  `backend/feed/services/schedule.py:144`,
  `backend/feed/models.py:209`, `backend/feed/models.py:235`).
- Schedule HTTP handling assumes successful responses and required headers
  (`backend/feed/services/schedule.py:54`,
  `backend/feed/services/schedule.py:55`,
  `backend/feed/services/schedule.py:61`,
  `backend/feed/services/schedule.py:64`).
- New Schedule feeds receive `feed_publisher` but not `transit_system`
  (`backend/feed/services/schedule.py:75`,
  `backend/feed/services/schedule.py:80`,
  `backend/feed/models.py:132`).
- `FeedMessage.timestamp` is declared with `auto_now=True`, although all three
  persistence functions pass the source header timestamp explicitly. Django's
  automatic save-time assignment wins over the constructor value, so source
  time is present in the generated primary-key string but not preserved in the
  timestamp field (`backend/feed/models.py:158`,
  `backend/feed/models.py:163`,
  `backend/feed/services/realtime.py:25`,
  `backend/feed/services/realtime.py:28`,
  `backend/feed/services/realtime.py:118`,
  `backend/feed/services/realtime.py:231`).
- `FeedMessage` stores metadata and normalized children but no raw protobuf
  payload (`backend/feed/models.py:158`,
  `backend/feed/models.py:165`).
- Alert deduplication is based on `entity_id` matches before per-alert writes;
  existing IDs are skipped rather than updated
  (`backend/feed/services/realtime.py:243`,
  `backend/feed/services/realtime.py:251`).
- Observability consists of Schedule informational logs and exporter return
  strings, without feed-owned Realtime logs or a status endpoint
  (`backend/feed/services/schedule.py:145`,
  `backend/feed/services/data.py:278`,
  `backend/feed/services/realtime.py:1`,
  `backend/feed/urls.py:1`).

### Broken

- Schedule import leaves `Feed.transit_system` unset, while
  `get_next_trips()` requires an exact `transit_system` match when selecting
  the current feed. A feed produced by this importer is therefore invisible
  to that query unless another process backfills the relationship
  (`backend/feed/services/schedule.py:75`,
  `backend/feed/services/schedule.py:80`,
  `backend/feed/models.py:132`,
  `backend/feed/services/queries.py:52`,
  `backend/feed/services/queries.py:53`).
- `VehiclePosition.trip_trip_id` does not allow `NULL`, while the persistence
  mapper assigns `None` when the protobuf omits `trip_id`
  (`backend/feed/models.py:682`,
  `backend/feed/services/realtime.py:46`).
- `get_next_trips()` computes a service ID, but the scheduled StopTime query's
  service filter is commented out; scheduled arrivals are therefore not
  restricted to the resolved service (`backend/feed/services/queries.py:75`,
  `backend/feed/services/queries.py:160`,
  `backend/feed/services/queries.py:165`).
- No feed migration is versioned in `HEAD`, while the repository ignores
  migration directories (`backend/feed/migrations/0001_initial.py:9`,
  `.gitignore:87`).

### Scaffolding

- `TripTime` explicitly carries a TODO to populate it during Schedule import,
  but the import map does not include it (`backend/feed/models.py:550`,
  `backend/feed/services/schedule.py:83`,
  `backend/feed/services/schedule.py:92`).
- `urls.py`, `views.py`, and `tests.py` contain only placeholders
  (`backend/feed/urls.py:1`, `backend/feed/views.py:3`,
  `backend/feed/tests.py:3`).

### Not found

- FareAttribute and FareRule ingestion
  (`backend/feed/models.py:368`, `backend/feed/models.py:386`,
  `backend/feed/services/schedule.py:83`,
  `backend/feed/services/schedule.py:92`).
- Schedule population of GeoShape, RouteStop, TripDuration, or TripTime
  (`backend/feed/models.py:428`, `backend/feed/models.py:460`,
  `backend/feed/models.py:498`, `backend/feed/models.py:548`,
  `backend/feed/services/schedule.py:83`,
  `backend/feed/services/schedule.py:92`).
- PostgreSQL or Parquet retention/cleanup; the only TTL reference is a TODO
  (`backend/feed/services/queries.py:90`).
- A feed-owned REST/DRF surface, WebSocket consumer, Celery task, event
  publisher, or Redis writer (`backend/feed/urls.py:1`,
  `backend/feed/views.py:3`,
  `backend/feed/services/realtime.py:1`,
  `backend/feed/services/realtime.py:19`).
- Implemented feed tests (`backend/feed/tests.py:1`,
  `backend/feed/tests.py:3`).

### Not verifiable

- Whether production publishers always return valid ZIP/protobuf payloads and
  the required Schedule headers; the importer directly assumes `ETag` and
  `Last-Modified` (`backend/feed/services/schedule.py:55`,
  `backend/feed/services/schedule.py:64`).
- Whether a deployed database already has tables equivalent to the ignored
  physical migration (`backend/feed/migrations/0001_initial.py:9`,
  `.gitignore:87`).
- Which `gtfs-django` revision a deployment receives because the entrypoint
  dynamically clones without a fixed commit
  (`backend/docker-entrypoint.sh:32`).
- Whether `/app/data` has sufficient space, permissions, backup, compaction,
  or external lifecycle management; the app only creates partitions and new
  files (`backend/feed/services/data.py:70`,
  `backend/feed/services/data.py:78`,
  `backend/feed/services/data.py:339`,
  `backend/feed/services/data.py:347`).

## Limitations and open decisions

### Known limitations

- **Broken VehiclePosition nullability:** `trip_trip_id` is required by the
  model but can be mapped to `None` from an optional protobuf field
  (`backend/feed/models.py:682`,
  `backend/feed/services/realtime.py:46`).
- **Source-time ambiguity:** `FeedMessage.timestamp` uses `auto_now=True`, so
  it records save time even though the services pass the GTFS header timestamp
  (`backend/feed/models.py:163`,
  `backend/feed/services/realtime.py:28`,
  `backend/feed/services/realtime.py:118`,
  `backend/feed/services/realtime.py:231`). The header timestamp remains
  embedded in the string primary key (`backend/feed/services/realtime.py:25`,
  `backend/feed/services/realtime.py:115`,
  `backend/feed/services/realtime.py:228`).
- **No raw Realtime archive:** `FeedMessage` has metadata fields only; raw
  protobuf bytes are not stored (`backend/feed/models.py:158`,
  `backend/feed/models.py:165`).
- **Unsafe Schedule cutover:** the old feed is deactivated before the new rows
  finish importing, without one encompassing transaction
  (`backend/feed/services/schedule.py:72`,
  `backend/feed/services/schedule.py:74`,
  `backend/feed/services/schedule.py:144`).
- **Missing imported stop geometry:** Schedule rows are bulk-created, so the
  custom `Stop.save()` that derives `stop_point` is not called and the importer
  does not set `stop_point` itself (`backend/feed/services/schedule.py:133`,
  `backend/feed/services/schedule.py:144`,
  `backend/feed/models.py:209`, `backend/feed/models.py:235`).
- **Fragile Schedule HTTP contract:** calls have no timeout or status check and
  required headers are indexed directly
  (`backend/feed/services/schedule.py:54`,
  `backend/feed/services/schedule.py:55`,
  `backend/feed/services/schedule.py:61`,
  `backend/feed/services/schedule.py:64`).
- **Incomplete Schedule ownership:** the new `Feed` is not assigned the
  publisher's transit system (`backend/feed/services/schedule.py:75`,
  `backend/feed/services/schedule.py:80`,
  `backend/feed/models.py:132`).
- **Incomplete Schedule model population:** fares and all four auxiliary
  models are outside the importer map
  (`backend/feed/services/schedule.py:83`,
  `backend/feed/services/schedule.py:92`,
  `backend/feed/models.py:368`, `backend/feed/models.py:386`,
  `backend/feed/models.py:428`, `backend/feed/models.py:460`,
  `backend/feed/models.py:498`, `backend/feed/models.py:548`).
- **Calendar/query correctness:** `get_calendar()` checks only added-service
  exceptions, and the resolved service ID is not applied to scheduled
  StopTimes (`backend/feed/services/queries.py:24`,
  `backend/feed/services/queries.py:25`,
  `backend/feed/services/queries.py:75`,
  `backend/feed/services/queries.py:165`).
- **Query scoping:** stop validation uses only `stop_id`, without the selected
  feed, while the latest Realtime `FeedMessage` is selected only by entity
  type, without publisher or transit-system scope
  (`backend/feed/services/queries.py:57`,
  `backend/feed/services/queries.py:85`,
  `backend/feed/services/queries.py:86`).
- **No retention:** PostgreSQL snapshots and UUID-named Parquet files have no
  feed-owned cleanup policy; the only TTL reference is a TODO
  (`backend/feed/services/queries.py:90`,
  `backend/feed/services/data.py:78`,
  `backend/feed/services/data.py:347`).
- **Migration and test gaps:** the physical initial migration is ignored and
  tests are placeholders (`backend/feed/migrations/0001_initial.py:9`,
  `.gitignore:87`, `backend/feed/tests.py:1`,
  `backend/feed/tests.py:3`).
- **Limited observability:** Realtime persistence has no logging and the app
  has no status endpoint (`backend/feed/services/realtime.py:1`,
  `backend/feed/services/realtime.py:19`,
  `backend/feed/urls.py:1`).

### Open decisions

1. **Schedule cutover:** decide whether download, validation, import, and
   current-feed switching should share one atomic or staged activation policy
   (`backend/feed/services/schedule.py:72`,
   `backend/feed/services/schedule.py:144`).
2. **HTTP resilience:** define timeouts, `raise_for_status()`, retry/backoff,
   authentication, required-header behavior, and payload validation for
   Schedule acquisition (`backend/feed/services/schedule.py:54`,
   `backend/feed/services/schedule.py:55`,
   `backend/feed/services/schedule.py:61`,
   `backend/feed/services/schedule.py:64`).
3. **Feed ownership:** decide whether `Feed.transit_system` should be copied
   from `FeedPublisher`, derived elsewhere, or removed as redundant
   (`backend/feed/models.py:60`, `backend/feed/models.py:132`,
   `backend/feed/services/schedule.py:80`).
4. **Schedule coverage:** decide whether fares and auxiliary models are
   production requirements, derived views, offline products, or removable
   schema (`backend/feed/models.py:368`, `backend/feed/models.py:386`,
   `backend/feed/models.py:428`, `backend/feed/models.py:460`,
   `backend/feed/models.py:498`, `backend/feed/models.py:548`).
5. **Realtime message identity:** decide whether `FeedMessage` represents
   source time, save time, one HTTP poll, or one unique source revision, and
   whether raw protobuf retention is required
   (`backend/feed/models.py:158`, `backend/feed/models.py:163`,
   `backend/feed/services/realtime.py:25`).
6. **Nullability contract:** decide whether VehiclePosition messages without a
   trip ID are valid and align the protobuf mapper and database constraint
   accordingly (`backend/feed/models.py:682`,
   `backend/feed/services/realtime.py:46`).
7. **Query semantics:** define correct calendar exception handling, service
   filtering, stop scoping, publisher scoping, and behavior for missing related
   trips/routes (`backend/feed/services/queries.py:24`,
   `backend/feed/services/queries.py:57`,
   `backend/feed/services/queries.py:85`,
   `backend/feed/services/queries.py:165`).
8. **Retention and lake management:** define PostgreSQL retention, Parquet
   compaction/deduplication, cleanup cadence, storage ownership, and recovery
   policy (`backend/feed/services/data.py:78`,
   `backend/feed/services/data.py:347`,
   `backend/feed/services/queries.py:90`).
9. **Migration policy:** decide how migrations will be committed and reconciled
   with databases that may already contain locally generated feed tables
   (`backend/feed/migrations/0001_initial.py:9`, `.gitignore:87`).
10. **External dependency pinning:** pin or otherwise record the deployed
    `gtfs-django` and `gtfs-io` revisions instead of dynamically cloning an
    unspecified revision (`backend/docker-entrypoint.sh:32`).
11. **Public boundary:** decide whether `feed` should remain an internal
    service/model app or expose a supported read API; its current URL and view
    modules are placeholders (`backend/feed/urls.py:1`,
    `backend/feed/views.py:3`).
