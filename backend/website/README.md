# Website

The `website` Django app is a small server-rendered presentation and manual
diagnostic surface for Infobús®. It provides four HTTP pages at the project
root: a development landing page, two static scaffolding pages, and an MBTA
stop-occupancy WebSocket test page.

The app describes its own landing page as **En desarrollo**. Nothing in the
current implementation establishes `website` as the production site for
Infobús®, and this document does not assign it that role.

Status terms in this document use the repository vocabulary: **implemented**,
**partial**, **broken**, **scaffolding**, **not found**, and **uncertain**.

## Purpose

**Overall status: partial.** The app currently has three concrete purposes:

1. Render a development landing page at `/` with links to the system and API
   documentation.
2. Reserve `/sobre/` and `/perfil/` as static scaffolding pages.
3. Provide a manual browser client at `/updates/` for selecting a current MBTA
   stop and subscribing to its occupancy topic through the `updates` WebSocket
   endpoint.

The implemented `/updates/` page is a diagnostic client. It does not own the
WebSocket consumer, subscription registry, topic parser, projection builders,
or message dispatch pipeline. Those responsibilities belong to `updates` and
are documented in `backend/updates/README.md`.

## Responsibilities and boundaries

### Responsibilities

- Register the four HTTP routes exposed by the app.
- Render the corresponding Django templates.
- Query `feed.Stop` for current, non-empty MBTA stop identifiers used by the
  manual updates page.
- Pass the selected transit-system code and stop list to `updates.html`.
- Build a stop-occupancy topic in the browser, open `/ws/updates/`, send the
  `subscribe` command, and display raw WebSocket messages.
- Register the app-owned `User` model in Django Admin.

### Boundaries

- `website` does not acquire, import, normalize, or persist GTFS Schedule or
  Realtime feeds. It only reads `feed.Stop` from one view.
- It does not implement the `/ws/updates/` protocol. The browser template is a
  consumer of the protocol documented by `updates`.
- It defines no DRF serializer, ViewSet, APIView, or JSON response contract.
- It defines no authentication or authorization requirement for any of its
  four routes.
- `/perfil/` does not read `request.user`, the app-owned `User` model, or any
  other profile data.
- The app-owned `User` model is not a replacement for Django's authentication
  user model.
- No current code establishes a supported production-site boundary for this
  app.

## Domain model and persistence

**Status: partial.** `website.models` defines a model named `User`, but its
database availability and intended application role are **uncertain**.

| Field | Current definition |
| --- | --- |
| `id` | Explicit `AutoField` primary key. |
| `user` | Optional one-to-one relation to Django's standard `auth.User`; deletion cascades. |
| `company` | Optional string with a maximum length of 100 characters. |
| `position` | Optional string with a maximum length of 100 characters. |

This class is an ordinary app model derived from `models.Model`. The project
does not configure it as `AUTH_USER_MODEL`, and no website view queries it.
`admin.py` registers the class, which makes the Admin registration
**implemented**, but does not prove that the backing table exists.

Migration ownership is **not found**. There is no physical or versioned
`backend/website/migrations/` directory at the documented HEAD, and the
repository-wide `migrations/` ignore rule applies to that path. A database may
already contain a locally created or historical table, but that state is
**uncertain** and cannot be reproduced from the tracked app files.

One model behavior is **broken** for a row allowed by its own schema:
`user` permits `NULL`, while `User.__str__()` unconditionally reads
`self.user.username`. Converting an instance without a linked auth user to a
string would therefore fail.

## Inputs

### HTTP inputs

The app receives requests at four root-mounted paths:

- `/`
- `/sobre/`
- `/perfil/`
- `/updates/`

The first three views do not consume query parameters, form data, request
bodies, or app-specific context. The profile route also does not consume
authenticated-user state.

### Feed input for `/updates/`

The `updates()` view reads `feed.Stop` rows whose related feed is current and
whose publisher belongs to transit-system code `mbta`. It excludes empty
`stop_id` values, orders by `stop_name` and `stop_id`, projects only those two
fields, and removes duplicate projected rows.

MBTA is a deliberate current filter and context value. It is not a fallback or
an example substituted by this documentation.

### Browser inputs for `/updates/`

After the page renders, the user selects one stop and activates the connection
button. The browser derives this topic:

```text
mbta.stop.occupancy_status.by_stop.<stop-id>
```

The template then sends the following command shape to the existing updates
WebSocket:

```json
{
  "action": "subscribe",
  "topic": "mbta.stop.occupancy_status.by_stop.<stop-id>"
}
```

Incoming WebSocket frames are browser-side inputs to the diagnostic page; they
are not processed by a Django `website` view.

## Outputs

| Template | Output | Status |
| --- | --- | --- |
| `index.html` | Development landing page with shared image assets, system-documentation and API-documentation links, and Bootstrap loaded from a CDN. | implemented |
| `about.html` | One static heading. | scaffolding |
| `profile.html` | One static profile heading with no user data. | scaffolding |
| `updates.html` | Stop selector, connection state, selected topic, and up to 200 raw WebSocket messages in the browser. | implemented |

All four outputs are server-rendered HTML. The app emits no app-owned JSON,
GeoJSON, file export, event, or WebSocket message format.

Templates do not use `{% extends %}` or `{% include %}`. There is no shared
website base template. `index.html` uses assets from the project-level
`backend/static/` directory, while its Bootstrap styles, icons, and JavaScript
come from external CDNs. `updates.html` keeps its CSS and JavaScript inline.

## Internal and external dependencies

### Internal dependencies

- `feed.models.Stop` supplies the stop list for `/updates/`. `website` consumes
  the model but does not own its schema or loading process.
- `updates` supplies the `/ws/updates/` consumer and subscription protocol.
  `website` only constructs a supported topic and sends a subscription command
  from the browser.
- `infobus.urls` mounts `website.urls` at the empty prefix.
- Project settings register `website.apps.WebsiteConfig`, configure Django
  templates, expose shared static files, and define the `website` logger.
- Django's standard `auth.User` is the target of the app-owned model's optional
  one-to-one relation.

### External dependencies

- Django supplies URL routing, function views, template rendering, the ORM,
  static-file template tags, and Django Admin.
- PostgreSQL/PostGIS is required for the `feed.Stop` query and would be required
  for `website.User` if its table exists.
- A browser with WebSocket support is required for the `/updates/` diagnostic
  flow.
- Bootstrap and Bootstrap Icons are loaded from `cdn.jsdelivr.net` by the
  landing page rather than from website-owned static files.

## Entrypoints

The project mounts `website.urls` with an empty prefix, so all app paths are
exposed directly from the backend root.

| Path | URL name | View | Template | Explicit context | Authentication | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | `index` | `index` | `index.html` | None | Not required | implemented |
| `/sobre/` | `about` | `about` | `about.html` | None | Not required | scaffolding |
| `/perfil/` | `profile` | `profile` | `profile.html` | None | Not required | scaffolding |
| `/updates/` | `updates_test` | `updates` | `updates.html` | `stops`, `transit_system` | Not required | implemented |

The Admin registration for `website.User` is another Django integration point,
but its database-backed operation is **uncertain** because no migration is
tracked.

`/ws/updates/` is not a website-owned entrypoint. It is an ASGI WebSocket
endpoint consumed by `updates.html`; its server-side behavior belongs to the
`updates` app.

## Main flow

### Static-page flow

1. Django resolves the root-mounted website URL.
2. `index()`, `about()`, or `profile()` calls `render()` with its corresponding
   template and no explicit app context.
3. Django renders the standalone template.

The profile flow ends at step 3. It does not look up or modify either
`auth.User` or `website.User`.

### Manual stop-occupancy flow

1. A browser requests `/updates/`.
2. `updates()` selects distinct current MBTA stops with non-empty identifiers.
3. The view renders `updates.html` with the stop projection and
   `transit_system="mbta"`.
4. The browser populates the stop selector from the rendered context.
5. When a stop is selected, JavaScript builds
   `mbta.stop.occupancy_status.by_stop.<stop-id>`.
6. The browser chooses `ws` or `wss` from the page protocol and opens exactly
   `${scheme}://${window.location.host}/ws/updates/`.
7. On connection, the browser sends the `subscribe` action and selected topic.
8. Subsequent frames are appended as raw text in the page, retaining the most
   recent 200 displayed messages.
9. Reconnecting closes the previous socket; leaving the page also disconnects
   it.

This flow validates a browser client's ability to consume the existing updates
protocol. It does not validate the internal event, projection, Redis, or
database paths owned by `updates`.

## Configuration

**Status: partial.** Configuration is mostly inherited from project-level
Django settings:

- `website.apps.WebsiteConfig` is present in `INSTALLED_APPS`.
- `infobus.urls` includes `website.urls` at the empty prefix.
- Django's `DjangoTemplates` backend uses `APP_DIRS=True`, allowing templates
  under `backend/website/templates/` to be discovered.
- Shared static assets are read from `backend/static/` and collected into the
  project static root.
- A `website` logging entry sends records to the console at the project
  `LOG_LEVEL`, with propagation disabled.

The MBTA transit-system code is hard-coded in both the database filter and
template context. No website-specific setting or environment variable selects
another transit system, so transit-system configuration is **not found**.

The project does not set `AUTH_USER_MODEL` to `website.User`. Authentication
middleware and the standard auth context processor may make authentication
state available to templates, but no website view enforces or consumes it.

## Operation and observability

**Status: partial.** Normal operation occurs inside the Django ASGI service.
Useful manual paths are:

```text
http://localhost:<backend-port>/
http://localhost:<backend-port>/sobre/
http://localhost:<backend-port>/perfil/
http://localhost:<backend-port>/updates/
```

The `/updates/` page provides visible connection states and displays raw
WebSocket messages. It can help an operator verify a selected MBTA subscription
manually, but it is not a health endpoint, metric, trace, structured log, or
automated readiness check.

Project settings define a console logger named `website`, but the app source
does not emit records through it. App-specific request logging, metrics,
tracing, error reporting, and a website-owned health endpoint are **not found**.
Operational diagnosis therefore depends on project/server logs, database
availability, browser developer tools, and the separate observability of
`feed` and `updates`.

The manual page cannot by itself distinguish among an empty MBTA stop catalog,
a database failure, a WebSocket routing failure, or missing upstream realtime
state. Those layers must be checked at their owning apps.

## Testing

**Status: partial.** `UpdatesPageTests` contains one implemented
`SimpleTestCase` for `/updates/`.

The test:

- mocks `website.views.Stop.objects.filter`, so it does not access the
  database;
- requests the named `updates_test` URL through Django's test client;
- checks for HTTP 200 and the mocked stop name;
- checks that the browser topic pattern is present in the rendered response;
- verifies the current-feed and MBTA filter arguments.

Run the focused module from `backend/` with:

```bash
uv run python manage.py test website
```

The current suite does not cover:

- `/`, `/sobre/`, or `/perfil/`;
- authentication or authorization behavior;
- `website.User`, its string conversion, or Django Admin;
- migration and clean-database behavior;
- real `feed.Stop` queries;
- a live `/ws/updates/` connection;
- shared static assets or external CDN loading.

The existing test is therefore useful rendering coverage for one diagnostic
page, not an integration test for website, feed, database, Channels, Redis, or
the updates pipeline.

## Integration status

**Overall status: partial.** The root landing page and the MBTA manual
WebSocket client are connected, while the profile/about routes, persistence,
testing, and observability remain incomplete or uncertain.

### Implemented

- Root mounting of the four website routes.
- Development landing-page rendering.
- The `/updates/` stop query, template context, topic construction, WebSocket
  connection, subscription command, connection status, and raw-message view.
- Consumption of the existing `/ws/updates/` endpoint using the current
  transit-system-scoped stop topic.
- Registration of `website.User` in Django Admin. This classification covers
  registration only, not the availability of its database table.

### Partial

- Test coverage: one database-free rendering test covers only `/updates/`.
- Operation and observability: a manual diagnostic UI exists, but automated
  health, metrics, traces, and app-emitted logs do not.
- Domain persistence: a model is declared and registered, but no reproducible
  migration path is tracked.
- Configuration: project template, static, and logging settings exist, while
  the MBTA selection remains hard-coded.

### Broken

- `website.User.__str__()` dereferences `self.user.username` even though the
  relation permits `NULL`; string conversion fails for that allowed row state.

### Scaffolding

- `/sobre/` renders only a static heading.
- `/perfil/` renders only a static heading and has no profile behavior.

### Not found

- Authentication or authorization enforcement on website routes.
- A consumer of `website.User` in website views.
- Versioned or physical website migrations.
- Website-owned static files.
- Template inheritance or includes.
- Tests for routes other than `/updates/`, the model, Admin, authentication, or
  live integration.
- App-emitted logs, metrics, traces, error reporting, or an app-specific health
  endpoint.

### Uncertain

- Whether the `website.User` table exists in any deployed database.
- Whether existing databases contain locally generated website migrations or
  schema history not represented in Git.
- The intended relationship among `/perfil/`, `website.User`, and standard
  Django authentication.
- The long-term supported role of the `website` app.

## Limitations and open decisions

### Known limitations

- The landing page explicitly remains in development.
- `/sobre/` and `/perfil/` are static scaffolding.
- No route requires authentication; `/perfil/` is not a user-profile feature.
- The app-owned model has no tracked migration and no website-view consumer.
- `User.__str__()` is incompatible with its nullable `user` relation.
- `/updates/` is hard-coded to MBTA and exposes a manual raw-message client.
- The diagnostic page covers one stop-occupancy topic family and does not
  validate the internal updates pipeline.
- Templates have no shared inheritance structure; CSS and JavaScript are
  either inline, project-shared, or CDN-hosted.
- Test coverage is limited to one mocked `/updates/` rendering path.
- App-specific observability is absent despite the project logger entry.

### Open decisions

12. **Define the supported role of `website`.** Decide whether this app should
    remain a development landing and diagnostic surface, become some other
    explicitly supported user-facing surface, or be replaced or removed. The
    current code does not establish it as the production site for Infobús®, and
    this decision must remain open until an explicit product and deployment
    boundary is adopted.

- **Profile and identity:** decide whether `/perfil/` should be removed, remain
  static, or become an authenticated feature, and whether `website.User` has
  any role in that design. Do not infer that role from the existing model name.
- **Migration policy:** decide whether the app-owned model should be retained,
  how its migrations will be versioned, and how any pre-existing database
  table will be reconciled with a reproducible migration history.
- **Model contract:** if the model remains, decide whether its auth-user
  relation may be null and make `__str__()` consistent with that decision.
- **Manual updates client:** decide whether the MBTA-only diagnostic page should
  remain public, require access control, support configurable transit systems,
  move to an operational tool, or be removed.
- **Template and asset strategy:** decide whether the standalone templates,
  shared static files, inline code, and CDN dependencies should remain or be
  consolidated under an explicit presentation architecture.
- **Verification and observability:** define the required route, model,
  migration, authentication, browser, WebSocket, logging, and health coverage
  once the supported role of the app is known.
