# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**Infobús** is a comprehensive Django-based real-time information system for public transportation displays. The system processes GTFS Realtime feeds and displays transit information on digital screens located at bus stops and stations throughout Costa Rica. The project is developed for Universidad de Costa Rica (UCR) and focuses on providing accessible, real-time public transport information.

## Architecture

This is a Django 5.2+ project with modern containerized infrastructure:

### 🚀 **Containerized Infrastructure**
- **Docker-based development and production environments**
- **Multi-stage Dockerfile** with optimized builds for dev/production
- **Docker Compose** orchestration for all services
- **Production-ready** with Nginx reverse proxy and security features

### 📱 **Django Applications**
- `website`: Main site pages, user management, and public interfaces
- `alerts`: Screen management, real-time data display via WebSockets
- `gtfs`: GTFS Schedule and Realtime data management (submodule: django-app-gtfs)
- `feed`: Information service providers and WebSocket consumers
- `api`: RESTful API endpoints with DRF integration

### 🛠️ **Technology Stack**
- **Backend**: Django 5.2+ with GeoDjango/PostGIS for geospatial operations
- **Real-time**: Django Channels + Daphne ASGI server for WebSocket connections
- **Background Tasks**: Celery + Redis for asynchronous task processing
- **Database**: PostgreSQL 16 with PostGIS 3.4 extension
- **Cache/Broker**: Redis 7 for sessions and Celery message broker
- **Web Server**: Nginx (production) with rate limiting and security headers
- **Transport Data**: GTFS Realtime bindings for transit data processing

### 🔧 **Key Dependencies**
The `gtfs` directory is a Git submodule pointing to `django-app-gtfs` which provides comprehensive GTFS data models and processing capabilities for Costa Rican transit data.

## Development Setup

### 🚀 **Quick Start with Docker (Recommended)**

**Prerequisites:**
- Docker Desktop
- Git

**One-command setup:**
```bash
./scripts/dev.sh
```

This will:
- Build and start all services (Django, PostgreSQL, Redis, Celery)
- Set up the database with PostGIS extension
- Run migrations and create sample data
- Start the development server with hot reload

**Access points:**
- Website: http://localhost:8000
- Admin: http://localhost:8000/admin (admin/admin)
- Database: localhost:5432
- Redis: localhost:6379

### 💻 **Manual Development Setup**

If you prefer to run services locally:

**Prerequisites:**
- Python 3.12+
- PostgreSQL 16+ with PostGIS 3.4+
- Redis 7+
- uv (Python package manager)

**Database Setup:**
```bash
# Create database
createdb infobus

# Enable PostGIS extension
psql infobus -c "CREATE EXTENSION postgis;"
```

**Environment Configuration:**
Create environment files (auto-created by scripts):
- `.env` - Base configuration
- `.env.dev` - Development overrides  
- `.env.local` - Local secrets (git-ignored)

**Example `.env.local`:**
```bash
SECRET_KEY=your-generated-secret-key
DEBUG=True
DB_NAME=infobus
DB_USER=postgres
DB_PASSWORD=postgres
REDIS_HOST=localhost
REDIS_PORT=6379
# macOS ARM64 GDAL/GEOS paths
GDAL_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/libgdal.so
GEOS_LIBRARY_PATH=/usr/lib/aarch64-linux-gnu/libgeos_c.so
```

## Common Commands

### 🚀 **Docker Development Workflow**

**Start Development Environment:**
```bash
./scripts/dev.sh  # One-command setup
```

**Common Development Tasks:**
```bash
# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f web
docker-compose logs -f celery-worker

# Run Django commands
docker-compose exec web uv run python manage.py migrate
docker-compose exec web uv run python manage.py createsuperuser
docker-compose exec web uv run python manage.py collectstatic

# Django shell
docker-compose exec web uv run python manage.py shell

# Run tests
docker-compose exec web uv run python manage.py test

# Stop environment
docker-compose down
```

### 🏭 **Production Deployment**

**Start Production Environment:**
```bash
./scripts/prod.sh  # Production setup with nginx
```

**Production Management:**
```bash
# View production logs
docker-compose -f docker-compose.production.yml logs -f

# Run migrations in production
docker-compose -f docker-compose.production.yml exec web uv run python manage.py migrate

# Collect static files
docker-compose -f docker-compose.production.yml exec web uv run python manage.py collectstatic

# Stop production environment
docker-compose -f docker-compose.production.yml down
```

**Production URLs:**
- Website: http://localhost (via Nginx)
- Admin: http://localhost/admin
- Health: http://localhost/health/

### 💻 **Manual Commands** (if not using Docker)

**Development Server:**
```bash
# Install dependencies
uv sync

# Run migrations
uv run python manage.py migrate

# Start Django server (Daphne ASGI)
uv run python manage.py runserver

# Start Celery worker
uv run celery -A datahub worker --loglevel=info

# Start Celery beat scheduler
uv run celery -A datahub beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info
```

### 📦 **Git Submodules**
```bash
# Initialize and update GTFS submodule
git submodule update --init --recursive

# Update submodule to latest
git submodule update --remote
```

### 📊 **Testing & Quality**
```bash
# Run all tests (in Docker)
docker-compose exec web uv run python manage.py test

# Run specific app tests
docker-compose exec web uv run python manage.py test alerts
docker-compose exec web uv run python manage.py test feed

# Code security scan
gitleaks detect --source . --verbose

# Check Docker services status
docker-compose ps
```

## Code Architecture

### Real-time Data Flow
1. **Data Collection**: Celery tasks periodically fetch GTFS Realtime feeds from external sources
2. **Data Processing**: GTFS data is processed and classified by relevance to specific screens/stops
3. **Real-time Updates**: Django Channels WebSockets push updates to connected display screens
4. **Display Rendering**: Raspberry Pi devices in kiosk mode display the information

### Screen Management System
- Screens are modeled with geographic locations (PostGIS Point fields)
- Each screen can display information from multiple transit agencies
- WebSocket connections maintain real-time updates to screen content
- Screens are designed for deployment on Raspberry Pi hardware in kiosk mode

### Background Tasks
Key Celery tasks include:
- `get_weather()`: Fetch weather data for display locations
- `get_social_feed()`: Collect relevant social media content
- `get_cap_alerts()`: Retrieve Common Alerting Protocol emergency alerts

### API Structure
- REST API endpoints are available at `/api/`
- GTFS-related endpoints at `/gtfs/`
- Screen status and WebSocket connections at `/status/`
- Alert management at `/alertas/`

## 🔧 **Troubleshooting**

### Database Migration Issues
If encountering migration problems:
```bash
# In Docker
docker-compose exec web uv run python manage.py migrate --fake <app> zero
docker-compose exec web uv run python manage.py makemigrations <app>
docker-compose exec web uv run python manage.py migrate

# Manual setup
uv run python manage.py migrate --fake <app> zero
uv run python manage.py makemigrations <app>
uv run python manage.py migrate
```

### Docker Issues
```bash
# Rebuild containers
docker-compose up --build

# Reset volumes (WARNING: deletes data)
docker-compose down -v

# Check container logs
docker-compose logs <service-name>

# Execute commands in running container
docker-compose exec web bash
```

### Environment File Issues
```bash
# Development scripts will auto-create missing files
./scripts/dev.sh  # Creates .env.dev and .env.local if missing

# Manual creation from templates
cp .env.local.example .env.local
# Edit .env.local with your settings
```

## 🏭 **Production Deployment**

### Docker Production Features
- **Containerized infrastructure** with Docker Compose
- **Multi-stage builds** optimized for production
- **Nginx reverse proxy** with rate limiting and security headers
- **PostgreSQL 16 with PostGIS 3.4** for geospatial data
- **Redis 7** for caching and Celery message broker
- **Celery workers and beat** for background task processing
- **Persistent data volumes** for database and media files
- **Environment-based configuration** with secure secrets management
- **Health check endpoints** for monitoring
- **SSL-ready configuration** (commented, ready to enable)

### Security Features
- **Rate limiting** on API and admin endpoints
- **Security headers** (OWASP recommended)
- **Content protection** and XSS prevention
- **Secrets isolation** (no secrets in git)
- **Container security** with non-root user

### Deployment Architecture
```
Internet → Nginx (Port 80) → Django/Daphne (Port 8000)
                           ↓
                    PostgreSQL (PostGIS)
                           ↓
                    Redis ← Celery Workers/Beat
```

### Production Checklist
- [ ] Generate secure `SECRET_KEY` in `.env.prod`
- [ ] Update database passwords
- [ ] Configure domain names in `ALLOWED_HOSTS`
- [ ] Set up SSL certificates (if needed)
- [ ] Configure backup strategy
- [ ] Set up monitoring and logging
- [ ] Test health check endpoints

**Designed for deployment on:**
- Cloud platforms (AWS, GCP, Azure)
- Virtual private servers
- Raspberry Pi display devices (kiosk mode)
- Local development and testing
