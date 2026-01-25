# WebSocket Module - GTFS-Realtime Broadcasting

**Author:** Brandon Trigueros Lara  
**Project:** TCU - SIMOVI Lab, Universidad de Costa Rica  
**Date:** January 2026

## Overview

This module implements real-time WebSocket broadcasting of GTFS-Realtime transit data using Django Channels and Celery.

## Architecture

```
Client (Browser)
    ↓ WebSocket (wss://infobus.ucr.ac.cr/ws/...)
Django Channels Consumer
    ↓ Channel Layer (Redis)
Celery Task (Broadcasting)
    ↓ Query Database
GTFS-Realtime Models
```

## Components

### Serializers (`serializers/gtfs.py`)
Convert Django ORM models to JSON following AsyncAPI 3.0 specification.

- `serialize_trip_update()` - TripUpdate + VehiclePosition
- `serialize_vehicle_position()` - VehiclePosition only
- `serialize_stop_time_update()` - StopTimeUpdate
- `serialize_route_vehicles()` - Snapshot of all vehicles on a route

### Consumers (`consumers/`)
Django Channels WebSocket consumers.

- **`TripConsumer`** ✅ (Completed) - Handles `ws/trips/{trip_id}` subscriptions
  - Query params: `include_stops` (bool), `include_shape` (bool)
  - Sends initial snapshot on connect
  - Receives broadcasts from channel layer
  - Error codes: 4001 (trip not found), 4002 (invalid params), 5001 (server error)
- **`RouteConsumer`** ⏳ (Pending) - Handles `ws/routes/{route_id}` subscriptions

### Tasks (`tasks.py`)
Celery tasks for broadcasting.

- `broadcast_trip_update()` - Triggered by `get_trip_updates()`
- `broadcast_route_update()` - Triggered by `get_vehicle_positions()`

## Quick Start

### Option 1: Automated Script (Recommended)

```bash
# Run the automated demo setup
./scripts/run_websocket_demo.sh
```

This script will:
1. ✅ Start Docker containers if not running
2. ✅ Create demo data if needed
3. ✅ Guide you to open the demo page
4. ✅ Optionally start the broadcast simulator

**Then open in your browser:**
- 🌐 Demo page: http://localhost:8000/websocket/demo/trip/
- 📊 Status check: http://localhost:8000/websocket/demo/status/

### Option 2: Manual Setup

```bash
# 1. Start containers
docker-compose up -d

# 2. Create demo data (first time only)
docker-compose exec web uv run python manage.py demo_websocket_data

# 3. Open browser
# Go to: http://localhost:8000/websocket/demo/trip/

# 4. In another terminal, start broadcast simulator
docker-compose exec web uv run python manage.py test_broadcast --count 15 --interval 3
```

### Features

- **Auto-detection**: WebSocket URL automatically uses current hostname
- **Multiple trips**: Select from dropdown if multiple demo trips exist
- **Real-time UI**: Live updates with connection status
- **Message log**: Debug console showing all WebSocket messages
- **No manual IP editing**: Works on localhost, WSL2, remote servers

## Usage

### Connecting to WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/trip/CR-SJ-01-123?include_stops=true');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Trip update:', data);
};
```

### Query Parameters

- `include_stops` (boolean): Include stop time updates (default: true)
- `include_shape` (boolean): Include route shape geometry (default: false)

## Testing

```bash
# Run all tests
pytest websocket/tests/

# Run serializers tests only (20 tests)
pytest websocket/tests/test_serializers.py -v

# Run consumers tests only (6 tests)
pytest websocket/tests/test_consumers.py -v

# Run with coverage
pytest websocket/tests/ --cov=websocket --cov-report=html
```

### Test Results

**TURNO 1 - Serializers:**
- 20/20 tests passing
- Coverage: >95%
- Files: test_serializers.py (358 lines)

**TURNO 2 - TripConsumer:**
- 6/6 tests passing
- Coverage: >85%
- Files: test_consumers.py (180 lines)

## Demo

### Quick Demo (Automated)

**One-line command:**
```bash
./scripts/run_websocket_demo.sh
```

**What it does:**
- Checks Docker is running
- Creates demo data if needed  
- Opens browser to demo page
- Optionally starts broadcast simulator

### Demo URLs

- **Trip Demo**: http://localhost:8000/websocket/demo/trip/
- **Status Check**: http://localhost:8000/websocket/demo/status/

### Manual Demo Steps

If you prefer manual control:

#### 1. Setup Demo Data

Create demo GTFS data (trip DEMO_SJ_HEREDIA_001):

```bash
docker-compose exec web uv run python manage.py demo_websocket_data
```

#### 2. Start Broadcast Simulator

Simulate real-time broadcasts every 3 seconds:

```bash
docker-compose exec web uv run python manage.py test_broadcast --count 15 --interval 3
```

Options:
- `--count N`: Number of broadcasts (default: 10)
- `--interval N`: Seconds between broadcasts (default: 5)
- `--trip-id ID`: Trip to broadcast (default: DEMO_SJ_HEREDIA_001)

#### 3. Open Demo Page

**Browser:** http://localhost:8000/websocket/demo/trip/

The page will:
- Auto-detect WebSocket URL (no IP editing needed)
- Auto-connect if demo data exists
- Show real-time updates with status indicators
- Log all WebSocket messages

### Old HTML Demo (Deprecated)

The static HTML file at `websocket/static/demo.html` is now **deprecated**.  
Use the Django-served demo instead for better experience.

### WSL2 Users

Browser should show:
- Connection status: "Conectado" (green)
- Trip ID: DEMO_SJ_HEREDIA_001
- Route ID: DEMO-SJ-HEREDIA
- Vehicle: Rápido 123 (BUS_123)
- Delay: Updating every 3 seconds (e.g., 309s → 368s → 420s...)
- Message log with timestamps

Console should show:
```
WebSocket connected
Received snapshot: {...}
Received update 1: delay=368s
Received update 2: delay=420s
...
```

## Implementation Status

- [x] **TURNO 1**: Serializers + Tests (Completed: Jan 23, 2026 - 20/20 tests passing)
- [x] **TURNO 2**: TripConsumer + Tests + Demo (Completed: Jan 24, 2026 - 6/6 tests passing)
- [ ] **TURNO 3**: RouteConsumer + Routing
- [ ] **TURNO 4**: Broadcasting Tasks

## AsyncAPI Specification

Full specification: `/docs/asyncapi/asyncapi-websocket-spec.yaml` (665 lines)

Channels:
- `ws/trip/{trip_id}` - Trip-specific updates
- `ws/route/{route_id}` - Route-wide vehicle positions
- `ws/route/{route_id}/direction/{direction_id}` - Direction-filtered

## References

- Django Channels: https://channels.readthedocs.io/
- AsyncAPI 3.0: https://www.asyncapi.com/docs/
- GTFS-Realtime: https://gtfs.org/realtime/
