# API Endpoint Security Audit

## 🔒 Protected Endpoints (Require Authentication)

### Admin Only
- `/admin/` - Django admin panel (superuser only)
- `/admin/api/metrics/` - API metrics dashboard (staff only, `@staff_member_required`)
- `/api/docs/schema/` - API schema (admin in production, public in dev)
- `/api/docs/` - ReDoc documentation (admin in production, public in dev)
- `/api/docs/swagger/` - Swagger UI (admin in production, public in dev)

### JWT Authentication Required
- `/api/auth/profile/` - User profile endpoint
- `/api/stops/` - GTFS stops (authenticated users)
- `/api/routes/` - GTFS routes (authenticated users)
- `/api/trips/` - GTFS trips (authenticated users)
- `/api/agencies/` - GTFS agencies (authenticated users)
- All ModelViewSet endpoints (authenticated users)

## 🌐 Public Endpoints (No Authentication Required)

### Authentication Endpoints
- `/api/auth/register/` - User registration (rate limited: 3/min)
- `/api/auth/login/` - User login (rate limited: 5/min)
- `/api/auth/refresh/` - Token refresh (rate limited: 20/min)

### Health & Monitoring
- `/api/health/` - Basic health check (rate limited: 100/min)
- `/api/ready/` - Readiness check (rate limited: 100/min)

### Transit Data (Public Access)
- `/api/search/` - Search stops and routes (rate limited: 30/min)
- `/api/arrivals/` - Real-time arrival predictions (rate limited: 60/min)
- `/api/schedule/departures/` - Scheduled departures (rate limited: 60/min)
- `/api/next-trips/` - Next trips information (rate limited: 60/min)
- `/api/next-stops/` - Next stops information (rate limited: 60/min)
- `/api/route-stops/` - Route stops information (rate limited: 60/min)
- `/api/status/` - System status (rate limited: 100/min)

## 🛡️ Rate Limiting Summary

### DRF Global Throttling
- **Anonymous users**: 60 requests/minute (all endpoints)
- **Authenticated users**: 200 requests/minute (all endpoints)

### Django-Ratelimit Custom Limits
- **public_light** (health, ready): 100/min
- **public_medium** (arrivals, schedule): 60/min
- **public_heavy** (search): 30/min
- **auth_sensitive** (login): 5/min
- **auth_register**: 3/min
- **auth_general** (profile): 20/min

## 🔐 Security Measures

### API Documentation Protection
✅ **Production**: Requires IsAdminUser (staff/superuser)
✅ **Development** (DEBUG=True): Public access for testing
✅ **Implementation**: Double-layered (SPECTACULAR_SETTINGS + URL permissions)

### CORS Protection
✅ Configurable via `CORS_ALLOWED_ORIGINS` environment variable
✅ Default: localhost:3000, localhost:8000
✅ Credentials allowed with proper origin validation

### Pagination Limits
✅ Default: 50 items per page
✅ Maximum: 1000 items per page
✅ Maximum offset: 10,000 (prevents deep pagination attacks)

### HTTP Security Headers
✅ ETag support for bandwidth optimization
✅ HSTS configuration available
✅ Content-Type sniffing protection
✅ XSS filter enabled
✅ Clickjacking protection

### Admin Dashboard Security
✅ API Metrics Dashboard protected with `@staff_member_required`
✅ Only staff/superuser accounts can access dashboard
✅ Non-authenticated users redirected to login
✅ Regular users denied access (requires is_staff=True)
✅ Comprehensive test coverage for access control

## ⚠️ Security Recommendations

### For Production Deployment

1. **Environment Variables** (`.env.prod`):
```bash
DEBUG=False
SECRET_KEY=<generate-strong-key>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

2. **API Documentation**:
   - ✅ Already secured (admin-only in production)
   - Consider disabling completely if not needed: Remove `/api/docs/*` URLs

3. **Rate Limiting**:
   - ✅ Already configured with sensible defaults
   - Monitor usage and adjust limits as needed
   - Consider IP whitelisting for known high-volume clients

4. **Database**:
   - Use strong PostgreSQL passwords
   - Restrict database access to application servers only
   - Enable PostgreSQL SSL connections

5. **Redis**:
   - Use Redis password (`requirepass` in redis.conf)
   - Restrict Redis access to localhost/app servers only

6. **Secrets Management**:
   - Never commit `.env.prod` or `.env.local` to git
   - Use environment-specific secrets in CI/CD
   - Rotate JWT SECRET_KEY periodically

## 📊 Security Testing

### Manual Tests
```bash
# Test Swagger is protected in production (should return 403)
curl -i http://production-domain.com/api/docs/swagger/

# Test public endpoints work
curl -i http://production-domain.com/api/health/

# Test rate limiting
for i in {1..70}; do curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/search/?q=test; done
```

### Automated Tests
- ✅ 113 tests passing (2 skipped)
- ✅ Security & performance tests included
- ✅ CORS, ETag, pagination, and rate limiting validated
- ✅ Admin dashboard access control validated

## 🔄 Security Update Log

### 2025-11-20 - Admin Metrics Dashboard
- Added API metrics dashboard at `/admin/api/metrics/`
- Protected with `@staff_member_required` decorator (staff/superuser only)
- Provides KPIs, charts, and analytics for API traffic
- Comprehensive test suite validates access control
- No sensitive data exposed to non-staff users

### 2025-11-14 - API Documentation Protection
- Added `IsAdminUser` permission to Swagger UI in production
- Added `IsAdminUser` permission to ReDoc in production  
- Added `IsAdminUser` permission to API schema in production
- Documentation remains public in DEBUG mode for development
- Double-layered protection: SPECTACULAR_SETTINGS + URL-level permissions

### Previous Security Features
- JWT authentication system
- Rate limiting (django-ratelimit + DRF throttling)
- CORS configuration
- ETag caching
- Pagination limits
- Client management and usage tracking
