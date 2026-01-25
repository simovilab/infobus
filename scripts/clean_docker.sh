#!/bin/bash
# Docker Cleanup Script
# 
# This script completely tears down Docker containers, volumes, and images.
# Use this to start fresh from a clean state.
# Usage: ./scripts/clean_docker.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${RED}🧹 Docker Cleanup Script${NC}"
echo "================================"
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will:${NC}"
echo "   • Stop all running containers"
echo "   • Remove all containers"
echo "   • Delete all volumes (DATABASE DATA WILL BE LOST)"
echo "   • Remove local Docker images"
echo ""
read -p "$(echo -e ${RED}Are you sure you want to continue? [y/N]:${NC} )" -n 1 -r
echo
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Cleanup cancelled. No changes made.${NC}"
    exit 0
fi

cd "$PROJECT_DIR"

echo -e "${BLUE}Step 1/4: Stopping containers...${NC}"
docker-compose stop 2>/dev/null || echo "No containers running"
echo -e "${GREEN}✓ Containers stopped${NC}"
echo ""

echo -e "${BLUE}Step 2/4: Removing containers...${NC}"
docker-compose rm -f 2>/dev/null || echo "No containers to remove"
echo -e "${GREEN}✓ Containers removed${NC}"
echo ""

echo -e "${BLUE}Step 3/4: Removing volumes (database, redis, static, media)...${NC}"
docker-compose down -v 2>/dev/null || echo "No volumes to remove"
echo -e "${GREEN}✓ Volumes removed${NC}"
echo ""

echo -e "${BLUE}Step 4/4: Removing local Docker images...${NC}"
docker-compose down --rmi local 2>/dev/null || echo "No local images to remove"
echo -e "${GREEN}✓ Images removed${NC}"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}✅ Cleanup complete!${NC}"
echo ""
echo -e "${BLUE}Docker state:${NC}"
docker-compose ps
echo ""
echo -e "${YELLOW}💡 To rebuild and start:${NC}"
echo "   docker-compose up -d --build"
echo "   docker-compose exec web uv run python manage.py migrate"
echo ""
