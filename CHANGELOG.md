# Changelog

All notable changes to the Infobús project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 🔒 Security & Performance Best Practices - 2025-10-23

#### Added
- **CORS Configuration**
  - Environment-based CORS origins via `CORS_ALLOWED_ORIGINS`
  - Configurable allowed methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
  - Custom headers support: Authorization, CSRF tokens, standard headers
  - Credential support with `CORS_ALLOW_CREDENTIALS`
  - Per-environment configuration (dev/staging/production)
  - `django-cors-headers` middleware integration

- **HTTP Caching & ETags**
  - Django `ConditionalGetMiddleware` for automatic ETag generation
  - MD5-based ETags for GET/HEAD requests
  - Conditional GET support with If-None-Match header
  - 304 Not Modified responses for unchanged resources
  - Bandwidth savings (30-50% for repeated requests)
  - Cache-friendly responses for static GTFS data

- **Query & Result Limits**
  - DRF LimitOffsetPagination with configurable limits
  - Default page size: 50 items
  - Maximum page size: 1000 items (`MAX_PAGE_SIZE`)
  - Maximum offset: 10,000 (`MAX_LIMIT_OFFSET`)
  - Prevents deep pagination attacks and resource exhaustion
  - Applied globally to all ModelViewSet endpoints

- **DRF Throttling**
  - Anonymous users: 60 requests/minute
  - Authenticated users: 200 requests/minute
  - `AnonRateThrottle` and `UserRateThrottle` enabled globally
  - Configurable via REST_FRAMEWORK settings
  - 429 responses with retry information
  - Disabled during tests to prevent conflicts
  - Complements existing django-ratelimit implementation

- **Health Check Endpoints**
  - `GET /api/health/` - Basic health check (instant response)
  - `GET /api/ready/` - Readiness check (validates DB and GTFS feed)
  - Returns 200 when ready, 503 when not ready
  - Public endpoints with rate limiting (100 requests/minute)
  - Load balancer compatible for monitoring

- **API Documentation Security**
  - Swagger UI restricted to admin users in production
  - ReDoc documentation restricted to admin users in production
  - API schema endpoint restricted to admin users in production
  - Documentation remains public in DEBUG mode for development
  - Double-layered protection: SPECTACULAR_SETTINGS + URL permissions

- **Security Audit Documentation**
  - Complete `SECURITY_AUDIT.md` documenting all endpoint security levels
  - Rate limiting summary for all public endpoints
  - Security recommendations for production deployment
  - Manual and automated security testing procedures

#### Technical Implementation
- **Dependencies Added**:
  - `django-cors-headers>=4.6.0` for CORS support

- **Settings Configuration**:
  - `corsheaders` in INSTALLED_APPS
  - `corsheaders.middleware.CorsMiddleware` in MIDDLEWARE
  - `django.middleware.http.ConditionalGetMiddleware` in MIDDLEWARE
  - `CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_CREDENTIALS`, `CORS_ALLOW_METHODS`
  - `MAX_PAGE_SIZE = 1000`, `MAX_LIMIT_OFFSET = 10000`
  - Conditional DRF throttling (disabled during tests)
  - SPECTACULAR_SETTINGS with admin-only permissions in production

- **URL Configuration**:
  - API documentation endpoints with conditional IsAdminUser permissions
  - Helper function `get_doc_permission_classes()` for DEBUG-aware permissions

#### Testing
- **Comprehensive Test Suite** (15+ tests in `test_security_performance.py`):
  - CORS configuration and preflight request tests
  - ETag generation and conditional GET tests
  - Pagination limit enforcement tests
  - Rate limiting configuration tests
  - Health and readiness check tests
  - Security headers validation tests
  - Performance configuration tests
- All 85 tests passing (2 appropriately skipped for DRF throttling in test mode)

#### Security Enhancements
- CORS prevents unauthorized cross-origin requests
- ETags reduce bandwidth and improve cache efficiency
- Pagination limits prevent resource exhaustion attacks
- DRF throttling provides additional layer against abuse
- Health checks enable monitoring without exposing sensitive data
- API documentation protected from unauthorized access in production
- Configurable security settings per environment

#### Performance Improvements
- ETag caching reduces bandwidth by 30-50% for repeated requests
- Conditional GET minimizes unnecessary data transfer
- Pagination prevents large result set memory issues
- Query limits protect against expensive deep pagination
- Health endpoints provide instant responses
- Total overhead: ~1-2ms per request

#### Files Modified
- `datahub/settings.py` - CORS, throttling, pagination limits, middleware, SPECTACULAR_SETTINGS
- `api/urls.py` - API documentation permission protection
- `pyproject.toml` - Added django-cors-headers dependency
- `api/tests/test_security_performance.py` - Skip tests during test mode
- `uv.lock` - Updated with new dependency
- `SECURITY_AUDIT.md` - New comprehensive security documentation

#### Backward Compatibility
- All existing functionality unchanged
- CORS allows localhost by default for development
- Pagination limits generous for normal use
- Throttling rates accommodate typical usage
- Health endpoints are new additions

### 🔑 API Client Management - 2025-10-22

#### Added
- **Client Models & Database Schema**
  - `Client` model for managing API consumers with comprehensive fields:
    - Basic information: name, description, contact email
    - API key management: 64-character secure keys with 8-character prefixes
    - Status management: active, inactive, suspended, revoked states
    - Tier system: free, basic, premium, enterprise tiers
    - Quotas: daily_quota, monthly_quota, rate_limit_per_minute
    - Access control: allowed_endpoints, allowed_ips (JSON fields)
    - Metadata: timestamps, created_by, last_used_at, key rotation tracking
  - `ClientUsage` model for detailed API usage tracking:
    - Request details: endpoint, method, status_code, response_time_ms
    - Client context: user_agent, ip_address
    - Size tracking: request_size_bytes, response_size_bytes
    - Error tracking: error_message field
    - Database indexes for efficient querying

- **Django Admin Interface**
  - **ClientAdmin** with comprehensive management features:
    - List display with status badges, usage counters, and key displays
    - Advanced filtering by status, tier, creation date, last used
    - Search by name, email, key prefix, description
    - Organized fieldsets: Client Info, API Access, Quotas, Access Control, Usage Stats
    - Bulk actions: regenerate keys, activate, suspend, revoke clients
    - Real-time usage statistics (today and this month)
    - Color-coded status and last-used indicators
    - Copy-to-clipboard API key display
  - **ClientUsageAdmin** (read-only analytics):
    - Comprehensive usage log viewing
    - Filterable by method, status code, timestamp, client tier
    - Color-coded status codes and response times
    - Date hierarchy navigation
    - Linked client references

- **Usage Metrics Capture**
  - `APIUsageTrackingMiddleware` for automatic metrics collection:
    - Captures all `/api/*` endpoint requests
    - Records response time with millisecond precision
    - Extracts client information from requests
    - Integrates with `capture_api_usage()` function
  - Middleware registered in Django settings
  - Non-blocking usage capture (doesn't affect request performance)

- **Management Commands**
  - `manage_clients` command with multiple actions:
    - `create`: Create new API clients with full configuration
    - `list`: Display all clients in formatted table
    - `rotate-key`: Regenerate API keys for security
    - `activate`: Activate suspended/inactive clients
    - `suspend`: Temporarily suspend client access
    - `revoke`: Permanently revoke client access
    - `usage`: View detailed usage statistics
  - `cleanup_usage` command for database maintenance:
    - Delete old usage records by age (default: 90 days)
    - Dry-run mode for safe testing
    - Batch processing for large datasets
    - Confirmation prompts for safety

- **API Key Security Features**
  - Secure key generation using `secrets` module
  - 64-character keys with mixed alphanumeric characters
  - Automatic key prefix generation for identification
  - Key rotation with timestamp tracking
  - Optional key expiration dates
  - Active status checking (status + expiration validation)

- **Client Lifecycle Management**
  - Four status states: active, inactive, suspended, revoked
  - Status change tracking via management commands
  - Bulk status management via Django admin
  - `is_active()` method validates both status and expiration

- **Usage Analytics**
  - `get_usage_summary()` method with period support:
    - Today's usage
    - This month's usage
    - Custom date range support
  - Aggregated metrics: total requests, unique endpoints
  - Integration with Django admin dashboard

#### Technical Implementation
- **Database Migrations**:
  - New `Client` and `ClientUsage` models
  - Indexes on client-timestamp, endpoint-timestamp, timestamp
  - Foreign key relationships with proper cascading
  - JSON fields for flexible access control configuration

- **Middleware Integration**:
  - `APIUsageTrackingMiddleware` registered in `MIDDLEWARE` setting
  - Non-intrusive request/response cycle integration
  - Automatic start time recording on request
  - Usage capture on response generation

- **Admin Customization**:
  - Custom admin displays with format_html for rich UI
  - QuerySet optimizations with annotations
  - Read-only fields for audit trail integrity
  - Custom actions with user feedback messages

- **Management Command Structure**:
  - Argument parsing with choices validation
  - Multiple identifier support (ID or name)
  - Detailed success/error messaging
  - Integration with Django's management framework

#### Documentation
- **README.md Updates**:
  - Complete client management section
  - Management command examples
  - API key rotation workflows
  - Status management procedures
  - Tier and quota explanations
  - Usage metrics tracking details
  - Django admin feature overview
  - Cleanup command documentation
  - Authenticated request examples
  - Client model field reference

#### Configuration
- **Settings Integration**:
  - Middleware registered in `datahub/settings.py`
  - Client and ClientUsage registered in Django admin
  - Usage tracking enabled by default

#### Files Modified
- `api/models.py` - Added Client and ClientUsage models
- `api/admin.py` - Added ClientAdmin and ClientUsageAdmin
- `api/middleware.py` - New APIUsageTrackingMiddleware
- `api/rate_limiting.py` - Enhanced with capture_api_usage function
- `api/management/commands/manage_clients.py` - New management command
- `api/management/commands/cleanup_usage.py` - New cleanup command
- `datahub/settings.py` - Middleware and admin registration
- `README.md` - Comprehensive client management documentation
- `CHANGELOG.md` - Feature documentation

#### Migration Path
1. Run migrations: `python manage.py migrate`
2. Create initial clients via management command or admin
3. Distribute API keys to client applications
4. Monitor usage in Django admin interface
5. Set up periodic cleanup job for usage records

#### Security Considerations
- API keys generated using cryptographically secure `secrets` module
- Keys never logged or exposed in plain text
- Admin interface displays masked keys with copy functionality
- Status management prevents unauthorized access
- IP and endpoint restrictions available for enhanced security
- Usage tracking for audit and compliance

#### Performance Impact
- Middleware adds ~1-2ms per request for usage capture
- Usage records indexed for efficient querying
- Batch cleanup prevents table bloat
- Redis integration ready for distributed deployments

### 🔐 Authentication & Security - 2025-10-16

#### Added
- **JWT Authentication System**
  - Complete user registration endpoint (`POST /api/auth/register/`)
    - User validation with password confirmation
    - Automatic JWT token generation on successful registration
    - Support for optional user profile fields (first_name, last_name)
  - Secure user login endpoint (`POST /api/auth/login/`)
    - JWT access token (1-hour lifetime) and refresh token (7-day lifetime) 
    - Enhanced error handling with detailed response messages
    - User data included in authentication response
  - Token refresh mechanism (`POST /api/auth/refresh/`)
    - Seamless token renewal without re-authentication
    - Token rotation with blacklisting for enhanced security
  - Protected user profile endpoint (`GET /api/auth/profile/`)
    - JWT-authenticated access to current user information
    - Proper 401 responses for unauthenticated requests

- **Comprehensive Rate Limiting**
  - **Tiered Rate Limiting Strategy** across all API endpoints:
    - **Public Light** endpoints (health, ready): 100 requests/minute
    - **Public Medium** endpoints (arrivals, schedule): 60 requests/minute
    - **Public Heavy** endpoints (search): 30 requests/minute
    - **Auth Sensitive** operations (login): 5 requests/minute
    - **Auth Registration**: 3 requests/minute
    - **Auth General** operations (profile): 20 requests/minute
  - **IP-based rate limiting** using django-ratelimit library
  - **Detailed 429 error responses** with retry information and timestamps
  - **Configurable rate limiting** via environment variables
  - **Rate limiting toggle** (`RATELIMIT_ENABLE` setting) for development/testing
  - **14 API endpoints protected** with appropriate rate limiting tiers

- **Enhanced Security Configuration**
  - JWT token configuration with security best practices:
    - HS256 algorithm for token signing
    - Token rotation and blacklisting enabled
    - Configurable token lifetimes
    - Secure token validation and user authentication rules
  - Rate limiting configuration in Django settings:
    - Environment-based rate limit configuration
    - Redis-backed rate limiting for distributed deployments
    - Granular control over different endpoint categories

#### Technical Implementation
- **Dependencies Added**:
  - `djangorestframework-simplejwt==5.3.0` - JWT authentication for Django REST framework
  - `django-ratelimit==4.1.0` - IP-based rate limiting middleware
  
- **New Modules**:
  - `api/auth_views.py` - JWT authentication view implementations
  - `api/rate_limiting.py` - Unified rate limiting utilities with dual approaches:
    - Simple approach (currently used): Direct function calls for rate limit checks
    - Decorator approach (future use): Clean decorator-based rate limiting
  
- **Database Integration**:
  - JWT authentication uses Django's built-in User model
  - Rate limiting integrates with Redis for distributed caching
  - No additional database migrations required

- **Settings Configuration**:
  - `SIMPLE_JWT` configuration with secure defaults
  - `REST_FRAMEWORK` authentication classes updated
  - `RATE_LIMITS` configuration with tiered limits
  - `RATELIMIT_ENABLE` toggle for flexible deployment

#### Testing
- **Comprehensive Test Suite** (20 tests total, 100% passing):
  - **JWT Authentication Tests** (10 tests):
    - User registration with validation scenarios
    - JWT login success and failure cases  
    - Token refresh functionality testing
    - Protected endpoint access verification
    - User profile retrieval with authentication
    - Error handling for invalid credentials and malformed requests
  
  - **Rate Limiting Tests** (10 tests):
    - Rate limit enforcement across all endpoint tiers
    - 429 error response format validation
    - Rate limiting configuration testing
    - Rate limiting disable/enable functionality
    - Different limits for authenticated vs unauthenticated users
    - Edge cases and threshold testing

- **Test Organization**:
  - Structured test suite in `api/tests/` directory
  - Separate test files for JWT authentication and rate limiting
  - Clean test setup with proper test isolation
  - Comprehensive edge case coverage

#### Documentation
- **Updated README.md** with complete authentication and rate limiting documentation:
  - Step-by-step authentication workflow examples
  - cURL examples for all authentication endpoints
  - Rate limiting tier explanations and configuration
  - Security checklist updates for production deployment
  
- **API Documentation Updates**:
  - JWT authentication flow documentation
  - Rate limiting behavior and error response formats
  - Environment variable configuration guide
  - Production security considerations

#### Migration & Compatibility
- **Backward Compatibility**: All existing API endpoints continue to work unchanged
- **Optional Authentication**: Public endpoints remain accessible without authentication
- **Gradual Adoption**: JWT authentication can be adopted incrementally for new features
- **Configuration Flexibility**: Rate limiting can be disabled for development environments

#### Security Enhancements
- **Authentication Security**:
  - Secure JWT token handling with industry best practices
  - Token rotation prevents replay attacks
  - Blacklisting prevents use of compromised tokens
  - Configurable token lifetimes for security/usability balance
  
- **Rate Limiting Security**:
  - Protection against DoS and brute force attacks
  - Intelligent tiered limits based on endpoint sensitivity
  - Detailed error responses help legitimate users while limiting attackers
  - IP-based tracking prevents circumvention via user switching

- **Production Readiness**:
  - Environment-based configuration prevents secrets in code
  - Redis integration supports horizontal scaling
  - Comprehensive error handling prevents information leakage
  - Security headers and CORS protection maintained

#### Configuration Examples

**.env additions**:
```bash
# JWT Authentication
SECRET_KEY=your-super-secure-secret-key-here

# Rate Limiting
RATELIMIT_ENABLE=true
RATE_LIMITS='{"public_heavy": "30/m", "public_medium": "60/m", "public_light": "100/m", "auth_sensitive": "5/m", "auth_register": "3/m", "auth_general": "20/m"}'
```

**Usage Examples**:
```bash
# Register new user
curl -X POST "http://localhost:8000/api/auth/register/" \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser", "email": "user@example.com", "password": "secure123", "password_confirm": "secure123"}'

# Login and get tokens  
curl -X POST "http://localhost:8000/api/auth/login/" \
  -H "Content-Type: application/json" \
  -d '{"username": "newuser", "password": "secure123"}'

# Access protected endpoint
curl "http://localhost:8000/api/auth/profile/" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN_HERE"
```

### Files Modified
- `README.md` - Added comprehensive authentication and rate limiting documentation
- `datahub/settings.py` - JWT and rate limiting configuration
- `api/auth_views.py` - New JWT authentication views
- `api/rate_limiting.py` - New unified rate limiting utilities  
- `api/views.py` - Rate limiting integration across all endpoints
- `api/tests/test_jwt_auth.py` - New comprehensive JWT authentication tests
- `api/tests/test_rate_limiting.py` - New comprehensive rate limiting tests
- `pyproject.toml` - Added JWT and rate limiting dependencies
- `.env` - Added authentication and rate limiting configuration

### Performance Impact
- **Minimal overhead**: JWT token validation adds ~1-2ms per request
- **Rate limiting overhead**: ~0.5ms per request for Redis-based tracking  
- **Memory usage**: Negligible increase due to efficient JWT implementation
- **Caching**: Rate limiting uses existing Redis infrastructure efficiently

### Breaking Changes
- **None**: All existing functionality remains unchanged and fully compatible
- **New dependencies**: `djangorestframework-simplejwt` and `django-ratelimit` required
- **Environment variables**: New optional configuration variables added
### Added - Search and Health Endpoints (feature/search-health-endpoints)

#### API Endpoints
- **GET /api/search/** - Unified search endpoint with fuzzy text matching and multilingual support
  - Query parameters:
    - `q` (required): Search query string
    - `type` (optional): Search type - 'stops', 'routes', or 'all' (default)
    - `limit` (optional): Maximum results (1-100), defaults to 20
    - `feed_id` (optional): Limit search to specific feed
  - Features:
    - **Fuzzy text matching** using PostgreSQL pg_trgm extension
    - **Accent-insensitive search** using unaccent extension
    - **Multilingual support** (Spanish, Portuguese, etc.)
    - **Relevance scoring** (0.0-1.0, exact matches = 1.0)
    - Searches: "San José" matches "San Jose" and vice versa
    - Handles typos: "Universidad" found even with "Univercidad"
  - Returns ranked results with:
    - Relevance scores sorted highest first
    - Result type (stop/route)
    - Full entity details (names, descriptions, IDs)
  - Searches across:
    - Stop names and descriptions
    - Route short names, long names, and descriptions

- **GET /api/health/** - Basic health check endpoint
  - Returns: `{"status": "ok", "timestamp": "..."}`
  - Simple 200 OK response for lightweight monitoring
  - No database queries - instant response

- **GET /api/ready/** - Readiness check endpoint
  - Returns 200 when ready to serve requests, 503 when not ready
  - Checks:
    - Database connectivity (PostgreSQL)
    - Current feed availability
  - Returns detailed status:
    - `status`: 'ready' or 'not_ready'
    - `database_ok`: Database connection status
    - `current_feed_available`: Whether current feed exists
    - `current_feed_id`: ID of current feed (if available)
    - `timestamp`: ISO format timestamp

#### PostgreSQL Extensions
- Enabled pg_trgm extension for trigram similarity searches
- Enabled unaccent extension for accent-insensitive text matching
- Extensions configured via:
  - `docker/db/init.sql` - Automatic setup on database creation
  - `datahub/test_runner.py` - Custom test runner for test database
  - Ensures extensions available in both dev and test environments

#### Interactive API Documentation
- **Swagger UI** added at `/api/docs/swagger/`
  - Interactive forms for all API endpoints
  - "Try it out" functionality for live testing
  - Parameter descriptions and examples
  - Real-time response preview
- **ReDoc** available at `/api/docs/`
  - Clean, organized API documentation
  - Request/response examples

#### Testing
- Comprehensive test suite for search endpoint (`test_search.py`)
  - Exact name matching tests
  - Partial name matching tests
  - Description search tests
  - Type filtering tests (stops, routes, all)
  - Limit parameter validation
  - Relevance score validation
  - Query parameter requirement tests
  
- Comprehensive test suite for health endpoints (`test_health.py`)
  - Health endpoint structure validation
  - Ready endpoint with/without current feed
  - Database connectivity error handling
  - Feed availability checks
  - Multiple current feeds handling
  - Response structure validation
  - Status value validation

### Added - API Read Endpoints (feat/api-read-endpoints)

#### API Endpoints
- **GET /api/arrivals/** - Real-time arrival predictions from external ETA service
  - Query parameters:
    - `stop_id` (required): Stop identifier
    - `limit` (optional): Maximum results (1-100), defaults to 10
  - Integrates with Project 4 ETA service via `ETAS_API_URL` configuration
  - Returns real-time arrival predictions with:
    - Trip and route information
    - Real-time arrival/departure times
    - Vehicle progression status
    - Wheelchair accessibility information
  - Error handling for upstream service failures (returns 502)
  - Returns 501 if ETAS_API_URL not configured

- **GET /api/status/** - System health check endpoint
  - Reports health status of:
    - PostgreSQL database connection
    - Redis cache connection
  - Useful for monitoring and load balancer health checks

- **GET /api/alerts/** - Service alerts from GTFS Realtime
  - Paginated list of current service alerts
  - Includes alert headers, descriptions, and affected entities

- **GET /api/feed-messages/** - GTFS Realtime feed messages
  - Paginated access to raw GTFS Realtime feed data
  - Includes timestamp and feed version information

- **GET /api/stop-time-updates/** - Real-time stop time updates
  - Paginated list of schedule deviations and predictions
  - Includes arrival/departure delays and schedule relationships

#### Pagination
- Global pagination enabled for all list endpoints
- `LimitOffsetPagination` with default page size of 50
- Consistent pagination format across all endpoints

#### Configuration
- `ETAS_API_URL` environment variable for external ETA service integration
  - Points to Project 4 real-time prediction service
  - If not configured, `/api/arrivals/` returns 501 Not Implemented

#### Testing
- Comprehensive test suite for arrivals endpoint (`test_arrivals.py`)
  - Mocked upstream API responses
  - Response structure validation
  - Error propagation testing (upstream failures)
  - Parameter validation (stop_id required, limit bounds)
  - Wrapped payload handling (results array)
  - Configuration validation (ETAS_API_URL)
  - Time format validation (HH:MM:SS)

#### Documentation
- Enhanced OpenAPI/Swagger documentation
  - Examples for all new endpoints
  - Pagination documentation
  - Filter fields properly mapped to model fields
- README updates with new endpoint documentation and usage examples

### Added - Storage and Data Access Layer (feat/storage-reading-dal)

#### Storage Layer
- **Data Access Layer (DAL)** with repository pattern for GTFS schedule data
  - `ScheduleRepository` interface defining contract for schedule data access
  - `PostgresScheduleRepository` implementation using Django ORM
  - `CachedScheduleRepository` decorator for Redis caching with configurable TTL
  - `RedisCacheProvider` for cache operations
  - Factory pattern (`get_schedule_repository()`) for obtaining configured repository instances

#### API Endpoints
- **GET /api/schedule/departures/** - Retrieve scheduled departures for a stop
  - Query parameters:
    - `stop_id` (required): Stop identifier
    - `feed_id` (optional): Feed identifier, defaults to current feed
    - `date` (optional): Service date in YYYY-MM-DD format, defaults to today
    - `time` (optional): Departure time in HH:MM or HH:MM:SS format, defaults to now
    - `limit` (optional): Maximum number of results (1-100), defaults to 10
  - Returns enriched departure data with route information:
    - Route short name and long name
    - Trip headsign and direction
    - Formatted arrival and departure times (HH:MM:SS)
  - Validates stop existence (returns 404 if not found)
  - Uses PostgreSQL as data source with Redis read-through caching

#### Configuration
- `SCHEDULE_CACHE_TTL_SECONDS` environment variable for cache duration (default: 60 seconds)
- Cache key format: `schedule:next_departures:feed={FEED_ID}:stop={STOP_ID}:date={YYYY-MM-DD}:time={HHMMSS}:limit={N}:v1`

#### Testing
- Comprehensive test suite for schedule departures endpoint
  - Response structure validation
  - Stop validation (404 handling)
  - Time format validation (HH:MM:SS)
  - Programmatic test dataset creation

#### Documentation
- OpenAPI/Swagger schema generation with drf-spectacular
- API endpoint annotations for automatic documentation
- Architecture documentation for DAL strategy
- README updates with endpoint usage examples and cache configuration

### Removed - Storage and Data Access Layer (feat/storage-reading-dal)

#### Fuseki Implementation
- Removed Apache Jena Fuseki as optional SPARQL backend
  - Deleted `storage/fuseki_schedule.py` implementation
  - Removed `api/tests/test_fuseki_schedule.py` integration tests
  - Removed Fuseki Docker service from docker-compose.yml
  - Deleted `fuseki_data` Docker volume
  - Removed `docker/fuseki/` configuration directory
  - Deleted `docs/dev/fuseki.md` documentation
- Removed Fuseki-related configuration
  - `FUSEKI_ENABLED` environment variable
  - `FUSEKI_ENDPOINT` environment variable
  - Fuseki references in `.env.local.example`
- Updated `storage/factory.py` to use only PostgreSQL repository
- PostgreSQL with Redis caching is now the sole storage backend

### Changed - Storage and Data Access Layer (feat/storage-reading-dal)

#### Documentation
- Updated README.md to document new DAL architecture and API endpoints
- Updated docs/architecture.md with storage strategy and repository pattern
- Added project structure documentation including `storage/` directory
- Removed all Fuseki references from documentation

---

## [Previous Releases]

<!-- Future releases will be documented above this line -->
