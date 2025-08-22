# Infobús

[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
<a href="https://github.com/psf/black/blob/main/LICENSE"><img alt="License: MIT" src="https://black.readthedocs.io/en/stable/_static/license.svg"></a>

Multi-tenant information distribution platform consuming GTFS Schedule and Realtime, and other real-time data to deliver passenger information across multiple channels. Provides GraphQL and RESTful APIs for trip planning, stop information and real-time arrivals, among others.

## Overview

Infobús processes GTFS Schedule and Realtime feeds and displays live transit information on digital screens located at bus stops and stations and other media. The system uses Django Channels for WebSocket connections to provide real-time updates.

## Features

- **Real-time Transit Data**: Processes GTFS Realtime feeds for live arrival/departure information
- **Digital Display Management**: Manages multiple screens with geographic positioning (PostGIS)
- **WebSocket Updates**: Live data streaming to connected displays
- **Multi-agency Support**: Handles transit data from multiple service providers
- **Weather Integration**: Displays weather conditions for screen locations
- **Social Media Feed**: Curated social media content relevant to transit users
- **Emergency Alerts**: Common Alerting Protocol (CAP) integration

## Technology Stack

- **Backend**: Django 5.0+ with GeoDjango/PostGIS
- **Real-time**: Django Channels + Daphne for WebSocket connections
- **Task Queue**: Celery + Redis for background processing
- **Database**: PostgreSQL with PostGIS extension
- **Transit Data**: GTFS Realtime bindings
- **Documentation**: MkDocs with Material theme

## Quick Start

1. **Setup Database**

   ```bash
   createdb datahub
   psql datahub -c "CREATE EXTENSION postgis;"
   ```

2. **Install Dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   Create `.env` file with database and Redis settings

4. **Initialize Submodules**

   ```bash
   git submodule update --init --recursive
   ```

5. **Run Migrations**

   ```bash
   python manage.py migrate
   ```

6. **Start Services**

   ```bash
   # Django server (with WebSocket support)
   python manage.py runserver

   # Celery worker (background tasks)
   celery -A datahub worker --loglevel=info

   # Celery beat (periodic tasks)
   celery -A datahub beat --scheduler django_celery_beat.schedulers:DatabaseScheduler --loglevel=info
   ```

## Architecture

The system follows a distributed architecture:

1. **Data Collection**: Celery tasks fetch GTFS Realtime feeds periodically
2. **Data Processing**: Information is classified and organized by screen relevance
3. **Real-time Distribution**: WebSockets push updates to connected displays
4. **Display Rendering**: Raspberry Pi devices in kiosk mode show the information

## Documentation

- Run `mkdocs serve` to view full documentation locally
- See `docs/` directory for detailed architecture and deployment guides
