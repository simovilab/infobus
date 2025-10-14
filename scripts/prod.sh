#!/bin/bash
# Production environment startup script for Infobus

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
        cat > nginx/nginx.conf << 'EOF'
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
EOF
    fi
fi

echo -e "${BLUE}🔧 Building production images...${NC}"

# Verify and ensure Docker access before running compose
ensure_docker_access "$@"

# Use production configuration
docker compose -f docker-compose.production.yml --env-file .env.prod --profile production up --build -d

echo ""
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 10

# Check if services are running
echo -e "${BLUE}🏥 Checking service status...${NC}"
if docker compose -f docker-compose.production.yml ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Production environment started successfully!${NC}"
else
    echo -e "${RED}⚠️  Some services may not be running properly. Check logs for details.${NC}"
fi

# Apply database migrations if needed
echo -e "${BLUE}💾 Applying database migrations...${NC}"
docker compose -f docker-compose.production.yml exec web uv run python manage.py migrate --noinput

# Collect static files
echo -e "${BLUE}📁 Collecting static files...${NC}"
docker compose -f docker-compose.production.yml exec web uv run python manage.py collectstatic --noinput

# Check basic health
echo -e "${BLUE}🏥 Testing application health...${NC}"
if curl -s -o /dev/null -w "%{http_code}" http://localhost/ | grep -q "200"; then
    echo -e "${GREEN}✅ Application is responding successfully!${NC}"
else
    echo -e "${RED}⚠️  Application health check failed. Check logs for details.${NC}"
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
echo "  Run migrations: docker compose -f docker-compose.production.yml exec web uv run python manage.py migrate"
echo "  Create superuser: docker compose -f docker-compose.production.yml exec web uv run python manage.py createsuperuser"
echo ""
echo -e "${RED}🛑 To stop: docker compose -f docker-compose.production.yml down${NC}"
