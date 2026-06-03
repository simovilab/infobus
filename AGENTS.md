# AGENTS.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**Infobús** is a real-time public transportation information system for Costa Rica, developed at Universidad de Costa Rica (UCR). It processes GTFS Schedule and Realtime feeds and delivers live transit information through digital displays at bus stops, a Nuxt web frontend, REST APIs, and WebSocket streams.

**Tech Stack:** Django 5.2+, Python 3.12+, Nuxt, PostgreSQL/PostGIS, Redis, RabbitMQ, Celery, FastMCP, Apache Jena Fuseki, Docker

## Architecture

### Services (Docker Compose)

1. **orchestrator** (Django / Daphne ASGI) — Control plane, REST API, admin, WebSockets
   - Django apps: `website`, `alerts`, `gtfs` (submodule), `engine`, `api`
   - Located in: `backend/`

2. **engine** (Celery worker) — Background task processing
   - Located in: `backend/` (same codebase, different entrypoint)

3. **scheduler** (Celery Beat) — Periodic task scheduling
   - Located in: `backend/`

4. **user-interface** (Nuxt) — Web frontend
   - Located in: `frontend/`

5. **context** (FastMCP) — MCP tool server
   - Located in: `context/`

6. **knowledge** (Apache Jena Fuseki) — SPARQL / knowledge graph
   - Located in: `knowledge/`

### Infrastructure Services

- **database** — PostgreSQL 16 with PostGIS 3.4 (durable persistence)
- **memory** — Redis 7 (cache, sessions, Celery broker)
- **broker** — RabbitMQ 4 (AMQP messaging)

### Key Dependencies

The `gtfs` directory in `backend/` is a Git submodule. Always run `git submodule update --init --recursive` after cloning.

## Development Commands

### Quick Start

```bash
./scripts/dev.sh  # builds, starts, and waits for all services
```

### Common Tasks

```bash
# Logs
docker compose -f compose.dev.yml logs -f
docker compose -f compose.dev.yml logs -f orchestrator

# Django management
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py migrate
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py createsuperuser
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py shell
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py collectstatic

# Stop
docker compose -f compose.dev.yml down
```

### Code Quality

```bash
# From backend/
ruff check .
ruff format .
mypy .
pytest
```

### Accessing Services

- Orchestrator / API: http://localhost:8000
- Django Admin: http://localhost:8000/admin (admin/admin)
- Nuxt frontend: http://localhost:3000
- RabbitMQ Management: http://localhost:15672 (guest/guest)
- Fuseki SPARQL: http://localhost:3030
- MCP Context: http://localhost:3278

## Production Deployment

Production uses Traefik as reverse proxy with Let's Encrypt TLS. All traffic via port 443.

```bash
./scripts/prod.sh
```

Compose file: `compose.prod.yml`

### Production Management

```bash
docker compose -f compose.prod.yml logs -f
docker compose -f compose.prod.yml exec orchestrator uv run python manage.py migrate
docker compose -f compose.prod.yml exec orchestrator uv run python manage.py createsuperuser
docker compose -f compose.prod.yml build && docker compose -f compose.prod.yml up -d
docker compose -f compose.prod.yml down
```

## Django Apps (backend/)

- **website** — Main site pages, user management, public interfaces
- **alerts** — Screen management, real-time data display via WebSockets
- **gtfs** — GTFS Schedule and Realtime data (Git submodule)
- **engine** — Information service providers and WebSocket consumers
- **api** — DRF ViewSets, token authentication, OpenAPI schema via drf-spectacular

### Background Tasks

Key Celery tasks:
- `get_weather()`: Fetch weather data for display locations
- `get_social_feed()`: Collect relevant social media content
- `get_cap_alerts()`: Retrieve Common Alerting Protocol emergency alerts

Scheduled via Django admin at `/admin/django_celery_beat/`.

### Screen Management

- Screens are modeled with geographic locations (PostGIS Point fields)
- Each screen can display information from multiple transit agencies
- WebSocket connections maintain real-time updates to screen content
- Designed for deployment on Raspberry Pi hardware in kiosk mode

## Environment Configuration

Required variables in `.env`:

- Django: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`
- Database: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`
- Redis: `REDIS_HOST`, `REDIS_PORT`
- RabbitMQ: `RABBITMQ_USER`, `RABBITMQ_PASS`, `RABBITMQ_HOST`, `RABBITMQ_PORT`
- macOS only: `GDAL_LIBRARY_PATH`, `GEOS_LIBRARY_PATH` (for PostGIS)

Files:

- `.env` — Base configuration (not in git)
- `.env.dev` — Development overrides (tracked)
- `.env.prod` — Production overrides (tracked)
- `.env.example` — Template

## Important Notes

- **GTFS submodule**: Always run `git submodule update --init --recursive` after cloning
- **Package manager**: Uses `uv`, not pip directly
- **Timezone**: `America/Costa_Rica` (es-cr locale)
- **Service names in Docker**: Use compose service names (`database`, `memory`, `broker`) not `localhost` for inter-service communication
- **Compose files**: `compose.dev.yml` (development), `compose.prod.yml` (production)
- **Production proxy**: Traefik (external container on `traefik_proxy` network), not Nginx
- **Tests**: Minimal coverage currently. Use pytest with pytest-django for new tests
