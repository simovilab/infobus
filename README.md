# Infobús

![Static Badge](https://img.shields.io/badge/backend-Django-white?logo=django)
![Static Badge](https://img.shields.io/badge/task_queue-Celery-white?logo=celery)
![Static Badge](https://img.shields.io/badge/package_manager-uv-white?logo=uv)
![Static Badge](https://img.shields.io/badge/frontend-Nuxt-white?logo=nuxt)
![Static Badge](https://img.shields.io/badge/database-PostgreSQL-white?logo=postgresql)
![Static Badge](https://img.shields.io/badge/memory-Redis-white?logo=redis)
![Static Badge](https://img.shields.io/badge/broker-RabbitMQ-white?logo=rabbitmq)
![Static Badge](https://img.shields.io/badge/mcp-FastMCP-white?logo=modelcontextprotocol)
![Static Badge](https://img.shields.io/badge/sparql-Fuseki-white?logo=apache)
![Static Badge](https://img.shields.io/badge/infrastructure-Docker-white?logo=docker)

A real-time public transportation information system, developed. Infobús processes GTFS Schedule and Realtime feeds and delivers live transit information through digital displays at bus stops, a web frontend, REST APIs, and WebSocket streams — all orchestrated through Docker Compose.

<img width="250" alt="infobus" src="https://github.com/user-attachments/assets/09695506-2392-4b9c-a89e-8d42d649ed21" />

## Architecture

| Service            | Role                                        | Tech                   |
| ------------------ | ------------------------------------------- | ---------------------- |
| **orchestrator**   | Control plane, REST API, admin, WebSockets  | Django / Daphne (ASGI) |
| **engine**         | Background task processing                  | Celery worker          |
| **scheduler**      | Triggers periodic tasks                     | Celery Beat            |
| **user-interface** | Web frontend                                | Nuxt                   |
| **database**       | Durable persistence with geospatial support | PostgreSQL + PostGIS   |
| **state**          | Cache, sessions, and Celery broker          | Redis                  |
| **broker**         | Async messaging                             | RabbitMQ               |
| **lake**           | Object storage                              | MinIO                  |

FastMCP, Fuseki, and the documentation site are deployed separately from the
development and production Compose stacks.

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed service mandates and design principles.

### Django apps (backend/)

- **website** — Main site pages, user management, public interfaces
- **alerts** — Screen management, real-time data display via WebSockets
- **gtfs** — GTFS Schedule and Realtime data (Git submodule)
- **engine** — Information service providers and WebSocket consumers
- **api** — RESTful API endpoints with DRF integration

### Data flow

1. Celery tasks periodically fetch GTFS Realtime feeds from transit agencies
2. Data is validated, processed, and classified by relevance to specific screens/stops
3. Django Channels WebSockets push live updates to connected display screens
4. Raspberry Pi devices in kiosk mode render the passenger information

## Getting Started

### Prerequisites

- Docker Engine 24+ and Docker Compose v2
- Git

### Setup

```bash
git clone https://github.com/simovilab/infobus.git
cd infobus
cp .env.example .env   # edit with your values
./scripts/dev.sh
```

The development stack includes licensed MinIO storage. Provide `minio.license`
in the repository root and set `MINIO_ROOT_PASSWORD` in `.env` before startup.

The startup script pulls images, builds containers, runs migrations, and performs basic service checks. On first run this takes 1–2 minutes.

### Development URLs

| URL                         | Description                       |
| --------------------------- | --------------------------------- |
| http://localhost:8001       | Orchestrator / API                |
| http://localhost:8001/admin | Django admin (admin/admin)        |
| http://localhost:8001/api/  | REST API root                     |
| http://localhost:3000       | Nuxt frontend                     |
| http://localhost:25672      | RabbitMQ management (guest/guest) |
| http://localhost:9000       | MinIO S3 API                      |
| http://localhost:9001       | MinIO console                     |

### Common commands

```bash
# Logs
docker compose -f compose.dev.yml logs -f              # all services
docker compose -f compose.dev.yml logs -f orchestrator  # single service

# Django management
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py migrate
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py createsuperuser
docker compose -f compose.dev.yml exec orchestrator uv run python manage.py shell

# Stop
docker compose -f compose.dev.yml down
```

### Code quality

```bash
# From backend/
ruff check .
ruff format .
mypy .
pytest
```

## Production Deployment

Production runs on Docker Compose behind a [Traefik](https://traefik.io/) reverse proxy that handles TLS termination via Let's Encrypt. All traffic goes through port **443**. No services expose ports directly to the host.

### Quick start

```bash
cp .env.example .env   # add production domains and credentials (see below)
./scripts/prod.sh
```

### Required environment variables

```bash
# Domain routing (Traefik)
ORCHESTRATOR_DOMAIN=api.example.com
UI_DOMAIN=app.example.com
LAKE_DOMAIN=lake.example.com
CERT_RESOLVER=letsencrypt

# Credentials
SECRET_KEY=<generate-a-strong-key>
DB_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>
RABBITMQ_USER=infobus
RABBITMQ_PASS=<strong-password>
MINIO_ROOT_USER=infobus
MINIO_ROOT_PASSWORD=<strong-password>
```

Provide the licensed `minio.license` file in the repository root before
starting the MinIO service. FastMCP, Fuseki, and the documentation site are
deployed separately and have their own domain configuration.

### Production services

| Service        | Domain variable       | Description                |
| -------------- | --------------------- | -------------------------- |
| orchestrator   | `ORCHESTRATOR_DOMAIN` | Django API and admin       |
| user-interface | `UI_DOMAIN`           | Nuxt frontend              |
| lake           | `LAKE_DOMAIN`         | MinIO S3-compatible API    |

Internal-only (not exposed): `database`, `state`, `engine`, `scheduler`, `broker`, and the MinIO console.

### Common operations

```bash
# Rebuild and restart after code changes
docker compose -f compose.prod.yml build orchestrator user-interface
docker compose -f compose.prod.yml up -d orchestrator user-interface

# Django management
docker compose -f compose.prod.yml exec orchestrator uv run python manage.py migrate
docker compose -f compose.prod.yml exec orchestrator uv run python manage.py createsuperuser

# Stop
docker compose -f compose.prod.yml down
```

## API

### REST endpoints

| Endpoint        | Description                               |
| --------------- | ----------------------------------------- |
| `/api/`         | API root (DRF browsable interface)        |
| `/api/gtfs/`    | GTFS Schedule and Realtime data           |
| `/api/alerts/`  | Screen management and alert systems       |
| `/api/weather/` | Weather information for display locations |

### WebSocket endpoints

| Endpoint      | Description                 |
| ------------- | --------------------------- |
| `/ws/alerts/` | Real-time screen updates    |
| `/ws/status/` | Live transit data streaming |

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — Service mandates and design principles
- [docs/](docs/) — Full documentation site (run locally or deployed at `DOCS_DOMAIN`)

## Contributing

See the [guidelines](https://github.com/simovilab/.github/blob/main/CONTRIBUTING.md).

## Contact

- Email: simovi@ucr.ac.cr
- Website: [simovi.org](https://simovi.org)

## License

Apache 2.0
