# MBTA Boston Demo Setup

This directory contains **demo-specific** setup scripts for Massachusetts Bay Transportation Authority (MBTA) data. These scripts are **NOT part of the production codebase** and serve only as examples for testing.

## Purpose

The Infobús real-time tracking system is **provider-agnostic**. This demo shows how to integrate with MBTA's GTFS-Realtime feeds as a proof-of-concept.

## Demo Scripts

### 1. `create_mbta_routes.py`
Creates MBTA routes in the database directly.

**Usage:**
```bash
docker compose exec celery-worker bash -c "cd /app && uv run python demos/mbta/create_mbta_routes.py"
```

**What it does:**
- Creates MBTA feed and agency
- Adds 10 common routes (Red, Blue, Orange, Green lines, buses)
- Only for initial demo setup

### 2. `load_mbta_routes.py`
Management command to load routes from MBTA's real-time protobuf feed.

**Usage:**
```bash
docker compose exec web uv run python manage.py load_mbta_routes
```

**What it does:**
- Fetches live VehiclePositions.pb from MBTA
- Extracts unique route IDs
- Creates Route objects automatically

## Integration with Production Code

The main Infobús system expects:
1. A configured `GTFSProvider` with URLs
2. Routes in the database (from GTFS Schedule or manual creation)
3. Celery tasks configured to fetch from provider URLs

For **production deployment**:
1. Configure your provider in admin panel
2. Import GTFS Schedule data (not covered by demo)
3. Configure Celery tasks with provider URLs
4. Deploy web client pointing to `/realtime/` endpoint

## Demo Configuration

To use MBTA demo data, set in your environment:

```python
# settings.py or environment variable
REALTIME_DEMO_PROVIDER = 'MBTA'
REALTIME_DEMO_CENTER = [42.3601, -71.0589]  # Boston coordinates
```

## Removing Demo Data

To clean up MBTA demo data:
```bash
docker compose exec web uv run python manage.py shell -c "
from gtfs.models import Route, Feed, Agency
Feed.objects.filter(feed_id__in=['mbta', 'MBTA_FEED']).delete()
"
```

## Adapting for Other Providers

1. Copy this directory: `cp -r demos/mbta demos/your_provider`
2. Update route metadata in scripts
3. Change URLs to your provider's feeds
4. Update README with provider-specific instructions

---

**Remember:** This is a **demo setup**, not production code. Production systems should load GTFS Schedule data through proper ETL pipelines.
