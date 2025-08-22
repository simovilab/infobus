# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**InfoBús** is a Django-based real-time information system for public transportation displays. The system processes GTFS Realtime feeds and displays transit information on digital screens located at bus stops and stations. The project is developed for Universidad de Costa Rica (UCR) and focuses on Costa Rica's public transport system.

## Architecture

This is a Django 5.0+ project with the following key components:

- **Django Apps**:
  - `website`: Main site pages and user management
  - `alerts`: Screen management and real-time data display via WebSockets
  - `gtfs`: GTFS Schedule and Realtime data management (submodule: django-app-gtfs)
  - `feed`: Information service providers and WebSocket consumers
  - `api`: REST API endpoints

- **Technology Stack**:
  - Django 5.0+ with GeoDjango/PostGIS for geospatial data
  - Django Channels + Daphne for WebSocket connections
  - Celery + Redis for background task processing
  - PostgreSQL with PostGIS extension
  - GTFS Realtime bindings for transit data processing

- **Key Dependencies**: The `gtfs` directory is a Git submodule pointing to `django-app-gtfs` which provides GTFS data models and processing capabilities.

## Development Setup

### Prerequisites
- Python 3.8+
- PostgreSQL with PostGIS extension
- Redis server
- Virtual environment

### Database Setup
```bash
# Create database
createdb datahub

# Enable PostGIS extension
psql datahub -c "CREATE EXTENSION postgis;"
```

### Environment Configuration
Create a `.env` file with required settings:
```bash
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
DB_NAME=datahub
DB_USER=your-db-user
REDIS_HOST=localhost
REDIS_PORT=6379
# macOS specific GDAL/GEOS paths if needed
GDAL_LIBRARY_PATH=/opt/homebrew/lib/libgdal.dylib
GEOS_LIBRARY_PATH=/opt/homebrew/lib/libgeos_c.dylib
```

## Common Commands

### Development Server
```bash
# Start Django development server (includes WebSocket support via Daphne)
python manage.py runserver

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic
```

### Background Services

**Celery Worker** (for background tasks):
```bash
celery -A datahub worker --loglevel=info
```

**Celery Beat** (for periodic tasks):
```bash
celery -A datahub beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info
```

**Redis Server** (if not running as service):
```bash
# On macOS
brew services start redis

# Test Redis connection
redis-cli ping
```

### Testing
```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test alerts
python manage.py test feed
python manage.py test api
```

### Documentation
```bash
# Serve documentation locally
mkdocs serve

# Build documentation
mkdocs build
```

### Git Submodules
```bash
# Initialize and update GTFS submodule
git submodule update --init --recursive

# Update submodule to latest
git submodule update --remote
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

## Database Migrations Issues
If encountering migration problems:
```bash
python manage.py migrate --fake <app> zero
# Remove migration files
python manage.py makemigrations <app>
python manage.py migrate
```

## Production Deployment Notes
- Uses `python-decouple` for environment-based configuration
- Requires PostgreSQL with PostGIS extension
- WebSocket support requires Redis for channel layers
- Static files served via `gunicorn` in production
- Designed for deployment on Raspberry Pi display devices
