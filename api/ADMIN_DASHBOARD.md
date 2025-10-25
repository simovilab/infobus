# Admin Dashboard Access Guide

## Quick Access

### 🎯 **Metrics Dashboard**
```
http://localhost:8000/admin/api/metrics/
```
Visual dashboard with charts showing:
- Traffic metrics (requests over time)
- Latency statistics  
- Error rates and recent errors
- Top endpoints
- Client usage breakdown

**Features:**
- Time range filter (Last Hour, 6 Hours, 24 Hours, 7 Days)
- Interactive Chart.js visualizations
- Recent errors table with drill-down
- KPI cards for quick insights

### 🔧 **Django Admin Panel**
```
http://localhost:8000/admin/
```
Standard Django admin with:
- Client management (CRUD operations)
- Usage logs (read-only analytics)
- Bulk actions (regenerate keys, activate, suspend, revoke)

## Authentication Required

You must be logged in as a **staff user** to access these pages:

1. **Superuser Login:**
   ```bash
   # Default credentials (development)
   Username: admin
   Password: admin
   ```

2. **Create New Admin User:**
   ```bash
   docker compose exec web uv run python manage.py createsuperuser
   ```

## Available Endpoints

### Admin Dashboard URLs

| URL | Description | Auth Required |
|-----|-------------|---------------|
| `/admin/` | Main admin panel | ✅ Staff |
| `/admin/api/metrics/` | Metrics dashboard | ✅ Staff |
| `/admin/api/metrics/endpoint/<path>/` | Endpoint detail view | ✅ Staff |
| `/admin/api/client/` | Client management | ✅ Staff |
| `/admin/api/clientusage/` | Usage logs | ✅ Staff |

### Time Range Filters

Add `?hours=X` query parameter to the metrics dashboard:

```
# Last hour
http://localhost:8000/admin/api/metrics/?hours=1

# Last 6 hours  
http://localhost:8000/admin/api/metrics/?hours=6

# Last 24 hours (default)
http://localhost:8000/admin/api/metrics/?hours=24

# Last 7 days
http://localhost:8000/admin/api/metrics/?hours=168
```

## Dashboard Features

### 📊 KPI Cards
- **Total Requests**: Count of all API requests in time range
- **Avg Latency**: Average response time in milliseconds
- **Success Rate**: Percentage of successful requests (< 400)
- **Error Rate**: Percentage of failed requests (≥ 400)
- **Client Errors**: Count of 4xx status codes
- **Server Errors**: Count of 5xx status codes
- **Active Clients**: Number of active API clients

### 📈 Charts
1. **Traffic Over Time**: Line chart showing request volume by hour
2. **Status Code Distribution**: Doughnut chart of HTTP status codes
3. **Request Methods**: Pie chart of GET, POST, PUT, DELETE, etc.
4. **Top 10 Endpoints**: Bar chart of most-requested endpoints
5. **Client Usage**: Bar chart showing requests per client

### 🔍 Drill-Down Tables
- **Recent Errors**: Last 20 errors with timestamp, endpoint, status, client, and error message
- Click on endpoint names to view detailed analytics (planned feature)

## Accessing from Custom Admin Index

When you visit `/admin/`, you'll see:
- Purple gradient card at the top with "View Metrics Dashboard" button
- Quick links sidebar with shortcuts to:
  - Manage API Clients
  - View Usage Logs  
  - Metrics Dashboard
  - API Documentation

## Troubleshooting

### "Page not found" error
- Ensure Docker containers are running: `docker compose ps`
- Check that migrations are applied: `docker compose exec web uv run python manage.py migrate`

### "Permission denied" error
- You need to be logged in as staff user
- Create superuser: `docker compose exec web uv run python manage.py createsuperuser`

### No data showing
- The dashboard shows data from `ClientUsage` model
- Generate some API traffic first:
  ```bash
  curl http://localhost:8000/api/health/
  curl http://localhost:8000/api/stops/
  ```

### Charts not displaying
- Check browser console for JavaScript errors
- Chart.js is loaded from CDN - ensure internet connection
- Try a different browser (Chrome/Firefox recommended)

## Development Notes

**Views Location**: `api/admin_dashboard.py`
**Templates**: `api/templates/admin/`
**URLs**: `api/admin_urls.py`

**Auth Decorator**: All views use `@staff_member_required`

## Future Enhancements (Planned)

- [ ] Export metrics to CSV/PDF
- [ ] Real-time updates with WebSockets
- [ ] Configurable alert thresholds
- [ ] Endpoint-specific detail pages
- [ ] Client comparison tools
- [ ] Custom date range picker
- [ ] Percentile calculations (P95, P99)
