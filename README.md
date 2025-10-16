# 🚌 Infobús

[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Django 5.2+](https://img.shields.io/badge/django-5.2+-green.svg)](https://djangoproject.com)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com/)

**Comprehensive real-time public transportation information system for Costa Rica**

Infobús is a modern Django-based platform that processes GTFS Schedule and Realtime feeds to deliver live transit information across multiple channels. Designed for Universidad de Costa Rica (UCR), it provides real-time passenger information through digital displays at bus stops and stations, APIs, and web interfaces.

## 🔍 Overview

Infobús is a production-ready, containerized platform that transforms raw GTFS transit data into accessible, real-time information for passengers across Costa Rica. The system processes multiple data sources and delivers information through various channels including digital displays, mobile apps, and web interfaces.

### Key Capabilities
- 🚍 **Real-time Transit Updates**: Live arrival/departure information from GTFS Realtime feeds
- 📺 **Digital Display Network**: Geographic screen management with PostGIS integration
- 🔄 **Live Data Streaming**: WebSocket-powered real-time updates to connected devices
- 🏢 **Multi-agency Support**: Unified platform for multiple transit providers
- 🌦️ **Weather Integration**: Location-based weather information for displays
- 📱 **Social Media Integration**: Curated transit-related social content
- 🆘 **Emergency Alerts**: CAP (Common Alerting Protocol) integration for critical updates

## ✨ Features

### 🏭 **Production Infrastructure**
- **Containerized Deployment**: Docker-based dev/production environments
- **Scalable Architecture**: Nginx reverse proxy with load balancing ready
- **High Availability**: Redis-backed caching and session management
- **Security Hardened**: Rate limiting, security headers, and container isolation
- **Monitoring Ready**: Health check endpoints and structured logging

### 📡 **Real-time Data Processing**
- **GTFS Realtime Integration**: Vehicle positions, trip updates, and service alerts
- **Background Task Processing**: Celery-powered async data collection
- **Geospatial Analysis**: PostGIS-enabled location-based services
- **Data Validation**: Robust data quality checks and error handling
- **Multi-source Aggregation**: Unified data from various transit agencies

### 🖥️ **Display Management**
- **Geographic Screen Positioning**: GPS-coordinated display locations
- **Dynamic Content Rendering**: Context-aware information display
- **WebSocket Live Updates**: Real-time screen content synchronization
- **Kiosk Mode Support**: Raspberry Pi deployment optimizations
- **Responsive Design**: Multi-device and screen size support

## 🛠️ Technology Stack

### 🔋 **Backend & APIs**
- **Django 5.2+**: Modern Python web framework with GeoDjango/PostGIS
- **Django REST Framework**: RESTful API development
- **Django Channels**: WebSocket support for real-time features
- **Daphne ASGI Server**: Production-ready async server
- **Python 3.12+**: Latest Python with modern async support

### 📊 **Data & Storage**
- **PostgreSQL 16**: Primary database with ACID compliance
- **PostGIS 3.4**: Advanced geospatial data processing
- **Redis 7**: High-performance caching and message broker
- **Docker Volumes**: Persistent data storage

### 🚪 **Infrastructure & Deployment**
- **Docker & Docker Compose**: Containerized development and production
- **Nginx**: Reverse proxy with security headers and rate limiting
- **Multi-stage Builds**: Optimized container images
- **uv**: Fast Python package management

### 🌐 **Real-time & Background Processing**
- **Celery**: Distributed task processing
- **Celery Beat**: Periodic task scheduling
- **WebSockets**: Live data streaming to displays
- **GTFS Realtime**: Transit data processing bindings

### 🔒 **Security & Monitoring**
- **JWT Authentication**: Secure token-based authentication for API access
- **Rate Limiting**: Comprehensive API protection with tiered limits
- **Environment-based Config**: Secure secrets management
- **Security Headers**: OWASP recommended protections
- **Health Checks**: Application and service monitoring

## 🚀 Quick Start

### Prerequisites
- **Docker Desktop** ([Download](https://www.docker.com/products/docker-desktop))
- **Git** ([Download](https://git-scm.com/downloads))
- **8GB+ RAM** recommended for all services

### 🛠️ Development Setup (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/simovilab/infobus.git
   cd infobus
   ```

2. **Initialize submodules**
   ```bash
   git submodule update --init --recursive
   ```

3. **Start development environment**
   ```bash
   ./scripts/dev.sh
   ```

   This single command will:
   - 📦 Build all Docker containers
   - 💾 Set up PostgreSQL with PostGIS
   - 🔄 Start Redis for caching
   - ⚙️ Run database migrations
   - 👥 Create admin user (admin/admin)
   - 🌐 Launch the development server with hot reload

4. **Access the application**
   - **Website**: http://localhost:8000
   - **Admin Panel**: http://localhost:8000/admin (admin/admin)
   - **API**: http://localhost:8000/api/

### 🏭 Production Deployment

1. **Configure production environment**
   ```bash
   # Copy and edit production settings
   cp .env.prod.example .env.prod
   # Generate a secure SECRET_KEY
   python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
   ```

2. **Start production environment**
   ```bash
   ./scripts/prod.sh
   ```

   Production includes:
   - 🌐 Nginx reverse proxy with SSL-ready config
   - 🛡️ Security headers and rate limiting
   - 📊 Performance optimizations and caching
   - 🔍 Health check endpoints

3. **Access production**
   - **Website**: http://localhost (via Nginx)
   - **Admin**: http://localhost/admin
   - **Health Check**: http://localhost/health/

### 📝 Common Commands

```bash
# View logs
docker-compose logs -f

# Run Django commands
docker-compose exec web uv run python manage.py migrate
docker-compose exec web uv run python manage.py createsuperuser
docker-compose exec web uv run python manage.py shell

# Run tests
docker-compose exec web uv run python manage.py test

# Stop all services
docker-compose down
```

## 🏧 Architecture

### 📊 Service Architecture

```
🌐 Internet → 🚪 Nginx (Port 80) → 🐍 Django/Daphne (Port 8000)
                                          ↓
                                   💾 PostgreSQL (PostGIS)
                                          ↓
                                   🔴 Redis ← 🐝 Celery Workers/Beat
```

### 🔄 Data Flow

1. **📡 Data Collection**: Celery tasks periodically fetch GTFS Realtime feeds from transit agencies
2. **⚙️ Data Processing**: Information is validated, processed, and classified by screen relevance
3. **📶 Real-time Distribution**: Django Channels WebSockets push live updates to connected displays
4. **🖥️ Display Rendering**: Raspberry Pi devices in kiosk mode render the passenger information

### 💱 Application Structure

- **`website`**: Main site pages, user management, and public interfaces
- **`alerts`**: Screen management, real-time data display via WebSockets
- **`gtfs`**: GTFS Schedule and Realtime data management (submodule: django-app-gtfs)
- **`feed`**: Information service providers and WebSocket consumers
- **`api`**: RESTful API endpoints with DRF integration

## 📚 API Documentation

### 🔐 Authentication

Infobús provides secure JWT-based authentication for API access:

#### User Registration
- **Endpoint**: POST /api/auth/register/
- **Purpose**: Create new user accounts with JWT token response
- **Required Fields**: username, email, password, password_confirm
- **Optional Fields**: first_name, last_name

```bash
curl -X POST "http://localhost:8000/api/auth/register/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "user@example.com",
    "password": "securepassword123",
    "password_confirm": "securepassword123"
  }'
```

#### User Login
- **Endpoint**: POST /api/auth/login/
- **Purpose**: Authenticate users and receive JWT access/refresh token pair
- **Returns**: Access token (1 hour), refresh token (7 days), user data

```bash
curl -X POST "http://localhost:8000/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "password": "securepassword123"
  }'
```

**Example Response**:
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 1,
    "username": "newuser",
    "email": "user@example.com",
    "first_name": "",
    "last_name": "",
    "date_joined": "2025-10-16T16:53:40.123456Z"
  }
}
```

#### Token Refresh
- **Endpoint**: POST /api/auth/refresh/
- **Purpose**: Refresh expired access tokens using valid refresh token

```bash
curl -X POST "http://localhost:8000/api/auth/refresh/" \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }'
```

#### Protected Endpoints
- **Endpoint**: GET /api/auth/profile/
- **Purpose**: Access current user profile (requires authentication)
- **Authorization**: Include JWT token in Authorization header

```bash
curl "http://localhost:8000/api/auth/profile/" \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

#### JWT Token Configuration
- **Access Token Lifetime**: 1 hour
- **Refresh Token Lifetime**: 7 days
- **Token Rotation**: Enabled (new refresh token issued on refresh)
- **Blacklisting**: Enabled (tokens invalidated after rotation)

### 🛡️ Rate Limiting

Comprehensive rate limiting protects all API endpoints with intelligent tiered limits:

#### Rate Limit Tiers
- **Public Light** (health, ready): 100 requests/minute
- **Public Medium** (arrivals, schedule): 60 requests/minute
- **Public Heavy** (search): 30 requests/minute
- **Auth Sensitive** (login): 5 requests/minute
- **Auth Registration**: 3 requests/minute
- **Auth General** (profile): 20 requests/minute

#### Rate Limit Headers & Responses
When rate limited, endpoints return HTTP 429 with detailed error information:

```json
{
  "error": "Rate limit exceeded",
  "details": "Too many requests. Please try again later.",
  "retry_after": 60,
  "limit_type": "requests_per_minute",
  "timestamp": "2025-10-16T16:53:40.123456Z"
}
```

#### Rate Limiting Configuration
- **Enable/Disable**: Set `RATELIMIT_ENABLE=true/false` in environment
- **Custom Limits**: Configure limits in `RATE_LIMITS` environment variable
- **IP-Based**: Rate limits applied per client IP address

### New: OpenAPI & Interactive Docs
- Redoc: http://localhost:8000/api/docs/
- OpenAPI schema (JSON): http://localhost:8000/api/docs/schema/

Examples have been added for the main read endpoints (paginated) and realtime helpers.

### Core Read Endpoints
- Stops (paginated): GET /api/stops/
- Routes (paginated): GET /api/routes/
- Trips (paginated): GET /api/trips/
- Alerts (paginated): GET /api/alerts/
- Arrivals/ETAs: GET /api/arrivals/?stop_id=...&limit=...
  - Requires ETAS_API_URL configured; returns 501 if not set
- Status: GET /api/status
  - Reports database_ok, redis_ok, fuseki_ok, current_feed_id, time
- Scheduled Departures (DAL-backed): GET /api/schedule/departures/

#### Curl examples
```bash
# Arrivals / ETAs (requires ETAS_API_URL)
curl "http://localhost:8000/api/arrivals/?stop_id=S1&limit=2"

# Service status
curl "http://localhost:8000/api/status/"
```

Pagination: enabled globally with LimitOffsetPagination (default page size 50).
Use `?limit=` and `?offset=` on list endpoints. Responses include
`{count, next, previous, results}`.

### New: Schedule Departures (Data Access Layer)
An HTTP endpoint backed by the new DAL returns scheduled departures at a stop. It uses PostgreSQL as the source of truth and Redis for caching (read-through) by default.

- Endpoint: GET /api/schedule/departures/
- Query params:
  - stop_id (required)
  - feed_id (optional; defaults to current feed)
  - date (optional; YYYY-MM-DD; defaults to today)
  - time (optional; HH:MM or HH:MM:SS; defaults to now)
  - limit (optional; default 10; max 100)

Example:
```bash
curl "http://localhost:8000/api/schedule/departures/?stop_id=STOP_123&limit=5"
```

Response shape:
```json
{
  "feed_id": "FEED_1",
  "stop_id": "STOP_123",
  "service_date": "2025-09-28",
  "from_time": "08:00:00",
  "limit": 5,
  "departures": [
    {
      "route_id": "R1",
      "route_short_name": "R1",
      "route_long_name": "Ruta 1 - Centro",
      "trip_id": "T1",
      "stop_id": "STOP_123",
      "headsign": "Terminal Central",
      "direction_id": 0,
      "arrival_time": "08:05:00",
      "departure_time": "08:06:00"
    }
  ]
}
```

Configuration flags (optional):
- FUSEKI_ENABLED=false
- FUSEKI_ENDPOINT=

### Using the optional Fuseki (SPARQL) backend in development

For development and tests, you can run an optional Apache Jena Fuseki server and point the app/tests at its SPARQL endpoint.

1) Start Fuseki
- docker-compose up -d fuseki
- The dataset is defined by docker/fuseki/configuration/dataset.ttl as "dataset" with SPARQL and graph store endpoints.
- Auth rules are controlled by docker/fuseki/shiro.ini (anon allowed for /dataset/sparql and /dataset/data in dev/tests).

2) Verify readiness
- GET: curl "http://localhost:3030/dataset/sparql?query=ASK%20%7B%7D"
- POST: curl -X POST -H 'Content-Type: application/sparql-query' --data 'ASK {}' http://localhost:3030/dataset/sparql

3) Admin UI
- http://localhost:3030/#/
- The mounted shiro.ini defines an Admin user by default. Also you can add users under [users] in that file if you need UI access, then recreate the container.

4) Using Fuseki from the app (optional)
- To have the app use Fuseki for reads instead of PostgreSQL, set these in .env.local:
  - FUSEKI_ENABLED=true
  - FUSEKI_ENDPOINT=http://fuseki:3030/dataset/sparql

5) Reset state (optional)
- The dataset persists in the fuseki_data Docker volume. To reset:
  - docker-compose stop fuseki
  - docker volume rm infobus_fuseki_data (name may vary)
  - docker-compose up -d fuseki

See also: docs/dev/fuseki.md for a deeper guide and troubleshooting.

Caching (keys and TTLs):
- Key pattern: schedule:next_departures:feed={FEED_ID}:stop={STOP_ID}:date={YYYY-MM-DD}:time={HHMMSS}:limit={N}:v1
- Default TTL: 60 seconds
- Configure TTL via env: SCHEDULE_CACHE_TTL_SECONDS=60

Arrivals smoke test (optional):
- A local script can mock the upstream ETAs service and call /api/arrivals/ end-to-end:
  ```bash
  python3 scripts/smoke_arrivals.py
  ```

### New: Search and Health Endpoints

#### Search API
Intelligent search for stops and routes with relevance ranking and fuzzy matching.

- **Endpoint**: GET /api/search/
- **Query Parameters**:
  - `q` (required): Search query string
  - `type` (optional): Search type - `stops`, `routes`, or `all` (default)
  - `limit` (optional): Max results (1-100, default 20)
  - `feed_id` (optional): Specific feed ID (defaults to current feed)

**Features**:
- 🎯 **Smart Relevance Scoring**: Exact matches score highest, followed by prefix matches, contains matches, and fuzzy similarity
- 🔍 **Multi-field Search**: Searches names, descriptions, and other relevant fields
- 🌐 **Unicode Support**: Handles special characters and accented text (José, Ñandú, etc.)
- ⚡ **PostgreSQL Trigram Similarity**: Advanced fuzzy matching with fallback to basic text search
- 🎛️ **Configurable Search Types**: Search stops only, routes only, or everything

```bash
# Search for stops containing "Central"
curl "http://localhost:8000/api/search/?q=Central&type=stops&limit=5"

# Search routes by short name "R1"
curl "http://localhost:8000/api/search/?q=R1&type=routes"

# Search everything (stops and routes)
curl "http://localhost:8000/api/search/?q=University"
```

**Example Response**:
```json
{
  "query": "Central",
  "results_type": "stops",
  "total_results": 2,
  "results": [
    {
      "stop_id": "STOP_001",
      "stop_name": "Central Station",
      "stop_desc": "Main central bus station",
      "stop_lat": "9.928100",
      "stop_lon": "-84.090700",
      "location_type": 0,
      "wheelchair_boarding": 1,
      "feed_id": "current_feed",
      "relevance_score": 1.0,
      "result_type": "stop"
    }
  ]
}
```

#### Health & Monitoring Endpoints
Two complementary health check endpoints for monitoring and load balancer integration.

**Simple Health Check**:
- **Endpoint**: GET /api/health/
- **Purpose**: Lightweight status check (always returns 200 OK if service is responding)
- **Use Case**: Basic uptime monitoring, load balancer health checks

```bash
curl "http://localhost:8000/api/health/"
# Returns: {"status": "ok", "timestamp": "2025-10-15T17:00:00Z"}
```

**Readiness Check**:
- **Endpoint**: GET /api/ready/
- **Purpose**: Comprehensive service readiness validation
- **Returns**: 200 if ready to serve requests, 503 if not ready
- **Use Case**: Kubernetes readiness probes, deployment validation

```bash
curl "http://localhost:8000/api/ready/"
# Returns 200 when ready:
# {
#   "status": "ready",
#   "database_ok": true,
#   "current_feed_available": true,
#   "current_feed_id": "current_feed",
#   "timestamp": "2025-10-15T17:00:00Z"
# }
#
# Returns 503 when not ready:
# {
#   "status": "not_ready",
#   "database_ok": true,
#   "current_feed_available": false,
#   "current_feed_id": null,
#   "timestamp": "2025-10-15T17:00:00Z"
# }
```

**Health Check Integration**:
```yaml
# Docker Compose health check
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/api/health/"]
  interval: 30s
  timeout: 10s
  retries: 3

# Kubernetes readiness probe
readinessProbe:
  httpGet:
    path: /api/ready/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

### Additional Realtime Collections
- Feed Messages (GTFS-RT metadata, paginated): GET /api/feed-messages/
- Stop Time Updates (realtime stop arrivals/departures, paginated): GET /api/stop-time-updates/

#### Curl examples
```bash
# Feed messages (paginated)
curl "http://localhost:8000/api/feed-messages/?limit=1"

# Stop time updates (paginated)
curl "http://localhost:8000/api/stop-time-updates/?limit=1"
```

### REST API Root
- **`/api/`** - Lists all registered endpoints with the DRF browsable interface

### WebSocket Endpoints
- **`/ws/alerts/`** - Real-time screen updates
- **`/ws/feed/`** - Live transit data streaming

## 🛠️ Development

### Project Structure
```
infobus/
├── 📁 scripts/          # Management scripts (dev.sh, prod.sh)
├── 📁 nginx/            # Nginx configuration
├── 📁 datahub/          # Django project settings
├── 📁 website/          # Main web application
├── 📁 alerts/           # Display and alert management
├── 📁 gtfs/             # GTFS data processing (submodule)
├── 📁 feed/             # Data feed management
├── 📁 api/              # REST API endpoints
├── 📁 storage/          # Data Access Layer (Postgres, Fuseki) and cache providers
├── 📦 docker-compose.yml              # Development environment
├── 📦 docker-compose.production.yml   # Production environment
├── 📄 Dockerfile         # Multi-stage container build
└── 📄 WARP.md           # AI assistant guidance
```

### Environment Configuration
- **`.env`** - Base configuration (committed)
- **`.env.dev`** - Development overrides (committed)
- **`.env.prod`** - Production template (committed, no secrets)
- **`.env.local`** - Local secrets (git-ignored)

Key variables:
- ETAS_API_URL: URL of the external Arrivals/ETAs service (Project 4). Required for /api/arrivals/.
  - If not set, the endpoint returns 501 Not Implemented.
- SCHEDULE_CACHE_TTL_SECONDS: TTL (seconds) for DAL schedule departures caching (default: 60).
- RATELIMIT_ENABLE: Enable/disable rate limiting (default: true).
- SECRET_KEY: Django secret key used for JWT token signing (required in production).

### Contributing
1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and test with `./scripts/dev.sh`
4. Run security scan: `gitleaks detect --source . --verbose`
5. Commit your changes: `git commit -m 'Add amazing feature'`
6. Push to the branch: `git push origin feature/amazing-feature`
7. Open a Pull Request

## 🧪 Testing

Run all tests (inside the web container):
```bash
docker-compose exec web uv run python manage.py test
```

Run only API tests (verbose):
```bash
docker-compose exec web uv run python manage.py test api --noinput --verbosity 2
```

Run only arrivals tests (these mock the upstream ETAs via requests.get, no external service required):
```bash
docker-compose exec web uv run python manage.py test api.tests.test_arrivals --noinput --verbosity 2
```

Optional local smoke test for arrivals (spins up a tiny local mock server and hits /api/arrivals):
```bash
python3 scripts/smoke_arrivals.py
```

## 🏢 Production Deployment

### Deployment Options
- **☁️ Cloud Platforms**: AWS, GCP, Azure with Docker
- **🖥️ VPS Deployment**: Ubuntu/CentOS with Docker Compose
- **🥰 Raspberry Pi**: Kiosk mode for display devices
- **💻 Local Development**: Full-featured local environment

### Security Checklist
- [ ] Generate secure `SECRET_KEY` in production
- [ ] Update database passwords
- [ ] Configure domain names in `ALLOWED_HOSTS`
- [ ] Set up SSL certificates
- [ ] Configure JWT token settings (`SIMPLE_JWT` in settings)
- [ ] Review rate limiting configuration (`RATE_LIMITS` in environment)
- [ ] Test authentication endpoints (/api/auth/*)
- [ ] Configure backup strategy
- [ ] Set up monitoring and logging
- [ ] Test health check endpoints

## 💫 Support & Community

### Getting Help
- **Documentation**: See `WARP.md` for detailed guidance
- **Scripts**: Use `./scripts/dev.sh --help` for command help
- **Health Checks**: Monitor `/health/` endpoint in production
- **Logs**: Use `docker-compose logs -f` for troubleshooting

### Built With Love ❤️
**Universidad de Costa Rica (UCR)** | **Laboratorio SIMOVI** | **Costa Rica**
