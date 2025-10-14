#!/bin/bash
# Production environment startup script for Infobus (Fixed for race conditions)

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Wait for a service to be healthy
wait_for_service() {
    local service_name="$1"
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}⏳ Waiting for ${service_name} to be ready...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if docker compose -f docker-compose.production.yml ps "$service_name" | grep -q "healthy\|Up"; then
            echo -e "${GREEN}✅ ${service_name} is ready!${NC}"
            return 0
        fi
        
        echo -e "${BLUE}   Attempt ${attempt}/${max_attempts}: ${service_name} not ready yet...${NC}"
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ ${service_name} failed to become ready after ${max_attempts} attempts${NC}"
    return 1
}

# Wait for web service to respond to HTTP requests
wait_for_web_ready() {
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}⏳ Waiting for web application to respond...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if docker compose -f docker-compose.production.yml $ENV_FILES exec -T web curl -f -s http://localhost:8000/health/ > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Web application is responding!${NC}"
            return 0
        fi
        
        echo -e "${BLUE}   Attempt ${attempt}/${max_attempts}: Web application not responding yet...${NC}"
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ Web application failed to respond after ${max_attempts} attempts${NC}"
    return 1
}

# Ensure current user can access Docker (Ubuntu/Linux friendly)
ensure_docker_access() {
    set +e

    if ! command -v docker >/dev/null 2>&1; then
        echo -e "${RED}❌ Docker is not installed or not in PATH.${NC}"
        echo "Please install Docker Engine and try again: https://docs.docker.com/engine/install/"
        exit 1
    fi

    # If Docker is already accessible, we're good
    if docker info >/dev/null 2>&1; then
        set -e
        return
    fi

    echo -e "${YELLOW}⚠️  Cannot access Docker daemon. Attempting to fix (may require sudo)...${NC}"

    # Only attempt group modifications on Linux systems
    if [ "$(uname -s)" != "Linux" ]; then
        echo -e "${YELLOW}ℹ️  Non-Linux system detected. Ensure Docker Desktop is running and retry.${NC}"
        if ! docker info >/dev/null 2>&1; then
            exit 1
        fi
    fi

    TARGET_USER="${SUDO_USER:-$USER}"

    # Create docker group if it doesn't exist
    if ! getent group docker >/dev/null 2>&1; then
        sudo groupadd docker
    fi

    # Add the invoking user to the docker group if needed
    if ! id -nG "$TARGET_USER" | grep -qw docker; then
        sudo usermod -aG docker "$TARGET_USER"
        ADDED_TO_GROUP=1
        echo -e "${BLUE}🧩 Added ${TARGET_USER} to 'docker' group.${NC}"
    fi

    # Restart Docker daemon
    if command -v systemctl >/dev/null 2>&1; then
        sudo systemctl restart docker || true
    else
        sudo service docker restart || true
    fi

    # If we just added the user to the docker group, re-exec the script in that context
    if [ "${ADDED_TO_GROUP:-0}" = "1" ]; then
        if command -v sg >/dev/null 2>&1; then
            echo -e "${YELLOW}🔁 Re-executing script with 'docker' group privileges...${NC}"
            if [ -n "$SUDO_USER" ]; then
                exec su - "$TARGET_USER" -c "sg docker -c '$0 $*'"
            else
                exec sg docker -c "$0 $*"
            fi
        else
            echo -e "${YELLOW}ℹ️  'sg' not available. Please log out and back in, or run: 'newgrp docker' then rerun this script.${NC}"
            exit 1
        fi
    fi

    # Final check
    if ! docker info >/dev/null 2>&1; then
        echo -e "${RED}❌ Still cannot access Docker. Try running with sudo: 'sudo $0' or verify the Docker service status.${NC}"
        exit 1
    fi

    set -e
}

echo -e "${GREEN}🏭 Starting Infobús in PRODUCTION mode...${NC}"
echo "Features enabled:"
echo "  - Nginx reverse proxy"
echo "  - Daphne ASGI server"
echo "  - Django Channels support"
echo "  - Static file caching"
echo "  - Security headers"
echo "  - Rate limiting"
echo "  - Optimized performance"
echo "  - PostGIS support"
echo ""

# Check if .env.prod exists
if [ ! -f ".env.prod" ]; then
    echo -e "${RED}❌ Error: .env.prod file not found!${NC}"
    echo "Please create .env.prod with your production settings."
    echo "You can copy from .env.prod.example (if available) and modify the values."
    exit 1
fi

# Check if production SECRET_KEY is still default
if grep -q "django-insecure-CHANGE-THIS-IN-PRODUCTION" .env.prod; then
    echo -e "${RED}⚠️  WARNING: You're using the default SECRET_KEY!${NC}"
    echo "Please generate a secure SECRET_KEY for production."
    echo "You can use: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if docker-compose.production.yml exists
if [ ! -f "docker-compose.production.yml" ]; then
    echo -e "${RED}❌ Error: docker-compose.production.yml file not found!${NC}"
    echo "The production configuration file is missing."
    exit 1
fi

# Check if nginx configuration directory exists
if [ ! -d "nginx" ]; then
    echo -e "${YELLOW}⚠️  Warning: nginx directory not found!${NC}"
    echo "Creating nginx configuration directory..."
    mkdir -p nginx/ssl
    
    # Create a basic nginx.conf if it doesn't exist
    if [ ! -f "nginx/nginx.conf" ]; then
        echo "Creating basic nginx.conf..."
        cat > nginx/nginx.conf << 'NGINXEOF'
# Nginx configuration for Infobus production deployment

upstream django {
    server web:8000;
}

# Rate limiting zones
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;

server {
    listen 80;
    server_name localhost;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: data: blob: 'unsafe-inline'" always;
    
    # Client max body size for file uploads
    client_max_body_size 50M;
    
    # Static files
    location /static/ {
        alias /var/www/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header Vary Accept-Encoding;
        
        # Gzip compression for static files
        gzip on;
        gzip_vary on;
        gzip_min_length 1000;
        gzip_types
            text/plain
            text/css
            text/xml
            text/javascript
            application/javascript
            application/xml+rss
            application/json;
    }
    
    # Media files
    location /media/ {
        alias /var/www/media/;
        expires 1d;
        add_header Cache-Control "public";
    }
    
    # Admin login rate limiting
    location /admin/login/ {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # API rate limiting
    location /api/ {
        limit_req zone=api burst=10 nodelay;
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Health check endpoint
    location = /health/ {
        access_log off;
        add_header Content-Type text/plain;
        return 200 "OK";
    }
    
    # Django application
    location / {
        proxy_pass http://django;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support for Django Channels
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Block access to sensitive files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }
}
NGINXEOF
    fi
fi


# Determine which env files to use
ENV_FILES="--env-file .env.prod"
if [ -f ".env.local" ]; then
    echo -e "${BLUE}📁 Found .env.local - using for local overrides (ALLOWED_HOSTS, etc.)${NC}"
    ENV_FILES="--env-file .env.prod --env-file .env.local"
else
    echo -e "${YELLOW}ℹ️  No .env.local found - using .env.prod only${NC}"
fi

echo -e "${BLUE}🔧 Building production images...${NC}"

# Verify and ensure Docker access before running compose
ensure_docker_access "$@"

# Phase 1: Start core infrastructure services first
echo -e "${BLUE}📦 Phase 1: Starting infrastructure services (DB, Redis)...${NC}"
docker compose -f docker-compose.production.yml $ENV_FILES up --build -d db redis

# Wait for infrastructure to be healthy
wait_for_service "db"
wait_for_service "redis"

# Phase 2: Build and prepare web service (but don't start nginx yet)
echo -e "${BLUE}🚀 Phase 2: Starting web application...${NC}"
docker compose -f docker-compose.production.yml $ENV_FILES up --build -d web

# Wait for web service container to be up
wait_for_service "web"

# Phase 3: Run database migrations and setup (only once, from script)
echo -e "${BLUE}💾 Phase 3: Setting up database...${NC}"
docker compose -f docker-compose.production.yml $ENV_FILES exec -T web uv run python manage.py migrate --noinput

# Create superuser if needed (non-interactively)
echo -e "${BLUE}👤 Creating superuser if needed...${NC}"
docker compose -f docker-compose.production.yml $ENV_FILES exec -T web uv run python manage.py shell << PYTHONEOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created: admin/admin')
else:
    print('Superuser already exists')
PYTHONEOF

# Collect static files
echo -e "${BLUE}📁 Collecting static files...${NC}"
docker compose -f docker-compose.production.yml $ENV_FILES exec -T web uv run python manage.py collectstatic --noinput

# Load any initial data
echo -e "${BLUE}📊 Loading initial data...${NC}"
docker compose -f docker-compose.production.yml $ENV_FILES exec -T web uv run python manage.py loaddata --ignorenonexistent || echo "No initial data found"

# Phase 4: Wait for web app to be fully ready to serve requests
wait_for_web_ready

# Phase 5: Start remaining services (Celery workers, beat, nginx)
echo -e "${BLUE}⚙️  Phase 4: Starting background services and proxy...${NC}"
docker compose -f docker-compose.production.yml $ENV_FILES --profile production up -d celery-worker celery-beat nginx

# Wait a moment for nginx to start and resolve service names
echo -e "${YELLOW}⏳ Allowing nginx to initialize...${NC}"
sleep 5

# Final health check
echo -e "${BLUE}🏥 Testing application health...${NC}"
MAX_HEALTH_ATTEMPTS=12
HEALTH_ATTEMPT=1

while [ $HEALTH_ATTEMPT -le $MAX_HEALTH_ATTEMPTS ]; do
    if curl -s -o /dev/null -w "%{http_code}" http://localhost/ | grep -q "200"; then
        echo -e "${GREEN}✅ Application is responding successfully!${NC}"
        break
    else
        echo -e "${BLUE}   Health check attempt ${HEALTH_ATTEMPT}/${MAX_HEALTH_ATTEMPTS}...${NC}"
        sleep 5
        HEALTH_ATTEMPT=$((HEALTH_ATTEMPT + 1))
    fi
done

if [ $HEALTH_ATTEMPT -gt $MAX_HEALTH_ATTEMPTS ]; then
    echo -e "${RED}⚠️  Application health check failed. Checking logs...${NC}"
    echo -e "${BLUE}Nginx logs:${NC}"
    docker compose -f docker-compose.production.yml logs --tail 10 nginx
    echo -e "${BLUE}Web logs:${NC}"
    docker compose -f docker-compose.production.yml logs --tail 10 web
else

# Phase 5: Optional SSL Setup
if [ -f ".env.local" ] && grep -q "^DOMAIN=" .env.local; then
    echo ""
    read -p "🔒 Would you like to set up HTTPS with SSL certificate? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ./scripts/setup-ssl.sh
    else
        echo -e "${YELLOW}ℹ️  SSL setup skipped. You can run ./scripts/setup-ssl.sh later${NC}"
    fi
fi

    echo -e "${GREEN}🎉 Production environment is fully operational!${NC}"
fi

echo ""
echo -e "${GREEN}🌐 Production URLs:${NC}"
echo "  Website: http://localhost (Nginx)"
echo "  Admin: http://localhost/admin"
echo "  API: http://localhost/api/"
echo "  Health: http://localhost/health/"
echo ""
echo -e "${BLUE}📊 Service endpoints:${NC}"
echo "  Database: localhost:5432 (postgres/postgres)"
echo "  Redis: localhost:6379"
echo ""
echo -e "${YELLOW}🔧 Production commands:${NC}"
echo "  View Nginx logs: docker compose -f docker-compose.production.yml logs nginx"
echo "  View app logs: docker compose -f docker-compose.production.yml logs web"
echo "  View all logs: docker compose -f docker-compose.production.yml logs -f"
echo "  Run migrations: docker compose -f docker-compose.production.yml $ENV_FILES exec web uv run python manage.py migrate"
echo "  Create superuser: docker compose -f docker-compose.production.yml $ENV_FILES exec web uv run python manage.py createsuperuser"
echo ""
echo -e "${RED}🛑 To stop: docker compose -f docker-compose.production.yml down${NC}"
