#!/bin/bash
# Development environment startup script for Infobus

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Starting Infobús in DEVELOPMENT mode...${NC}"
echo "Features enabled:"
echo "  - Live reloading"
echo "  - Debug mode"
echo "  - Volume mounting for code changes"
echo "  - Django development server (Daphne)"
echo "  - Hot reload with watchdog"
echo ""

# Check if required env files exist
if [ ! -f ".env" ]; then
    echo -e "${RED}❌ Error: .env file not found!${NC}"
    echo "Please create .env with base configuration."
    exit 1
fi

if [ ! -f ".env.dev" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env.dev file not found!${NC}"
    echo "Creating minimal .env.dev file..."
    cat > .env.dev << EOF
# Development Environment Configuration
# This file contains development-specific overrides

# Enable debug mode for development
DEBUG=True

# Verbose logging for development
LOG_LEVEL=DEBUG

# Additional allowed hosts for development
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,*.ngrok.io,*.localhost
EOF
fi

if [ ! -f ".env.local" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env.local file not found!${NC}"
    echo "Creating .env.local from example..."
    cp .env.local.example .env.local
fi

echo -e "${BLUE}🔧 Building development environment...${NC}"

# Use the base docker-compose.yml which is configured for development
# Docker Compose will automatically load .env, .env.dev, and .env.local in order
docker-compose up --build -d

echo ""
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 5

# Check if services are running
echo -e "${BLUE}🏥 Checking service status...${NC}"
if docker-compose ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Development environment started successfully!${NC}"
else
    echo -e "${RED}⚠️  Some services may not be running properly. Check logs for details.${NC}"
fi

echo ""
echo -e "${GREEN}🌐 Development URLs:${NC}"
echo "  Website: http://localhost:8000"
echo "  Admin: http://localhost:8000/admin (admin/admin)"
echo "  API: http://localhost:8000/api/"
echo ""
echo -e "${BLUE}📊 Service endpoints:${NC}"
echo "  Database: localhost:5432 (postgres/postgres)"
echo "  Redis: localhost:6379"
echo ""
echo -e "${YELLOW}🔧 Development commands:${NC}"
echo "  View logs: docker-compose logs -f"
echo "  View web logs: docker-compose logs -f web"
echo "  Run migrations: docker-compose exec web uv run python manage.py migrate"
echo "  Create superuser: docker-compose exec web uv run python manage.py createsuperuser"
echo "  Django shell: docker-compose exec web uv run python manage.py shell"
echo ""
echo -e "${RED}🛑 To stop: docker-compose down${NC}"
