#!/bin/bash
# WebSocket Demo Setup Script
# 
# This script automates the setup and running of the WebSocket demo.
# Usage: ./scripts/run_websocket_demo.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🚀 WebSocket Demo Setup"
echo "======================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if docker-compose is running
if ! docker-compose ps | grep -q "web.*Up"; then
    echo -e "${YELLOW}⚠️  Docker containers not running${NC}"
    echo -e "${BLUE}Starting containers...${NC}"
    cd "$PROJECT_DIR"
    docker-compose up -d
    echo -e "${GREEN}✓ Containers started${NC}"
    echo -e "${YELLOW}Waiting 10 seconds for services to be ready...${NC}"
    sleep 10
else
    echo -e "${GREEN}✓ Docker containers running${NC}"
fi

echo ""

# Run migrations
echo -e "${BLUE}Running database migrations...${NC}"
docker-compose exec -T web uv run python manage.py migrate --noinput
echo -e "${GREEN}✓ Migrations complete${NC}"

echo ""

# Check if demo data exists
echo -e "${BLUE}Checking for demo data...${NC}"
DEMO_EXISTS=$(docker-compose exec -T web uv run python manage.py shell -c "
from gtfs.models import TripUpdate
print(TripUpdate.objects.filter(trip_trip_id__startswith='DEMO_').exists())
" 2>/dev/null | tail -1 || echo "False")

if [ "$DEMO_EXISTS" = "True" ]; then
    echo -e "${GREEN}✓ Demo data already exists${NC}"
else
    echo -e "${YELLOW}⚠️  No demo data found${NC}"
    echo -e "${BLUE}Creating demo data...${NC}"
    docker-compose exec web uv run python manage.py demo_websocket_data
    echo -e "${GREEN}✓ Demo data created${NC}"
fi

echo ""
echo -e "${GREEN}✓ Setup complete!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${BLUE}📋 Next steps:${NC}"
echo ""
echo -e "1️⃣  ${GREEN}Open the demo in your browser:${NC}"
echo "   http://localhost:8000/websocket/demo/trip/"
echo ""
echo -e "2️⃣  ${GREEN}In a separate terminal, start the broadcast simulator:${NC}"
echo "   cd $PROJECT_DIR"
echo "   docker-compose exec web uv run python manage.py test_broadcast --count 15 --interval 3"
echo ""
echo -e "3️⃣  ${GREEN}Watch real-time updates in the browser!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${YELLOW}💡 Tips:${NC}"
echo "   • The page auto-connects if demo data exists"
echo "   • You can select different trips from the dropdown"
echo "   • Run test_broadcast multiple times to see updates"
echo "   • Check the message log for debugging"
echo ""
echo -e "${BLUE}📊 Demo Status Endpoint:${NC}"
echo "   http://localhost:8000/websocket/demo/status/"
echo ""

# Ask if user wants to open browser
read -p "$(echo -e ${BLUE}Do you want to open the demo in your browser now? [y/N]:${NC} )" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Try to detect OS and open browser
    if command -v xdg-open &> /dev/null; then
        xdg-open "http://localhost:8000/websocket/demo/trip/" &
    elif command -v open &> /dev/null; then
        open "http://localhost:8000/websocket/demo/trip/" &
    elif [ -f /mnt/c/Windows/System32/cmd.exe ]; then
        # WSL2 - open in Windows browser
        /mnt/c/Windows/System32/cmd.exe /c start "http://localhost:8000/websocket/demo/trip/" &
    else
        echo -e "${YELLOW}Could not detect browser. Please open manually:${NC}"
        echo "http://localhost:8000/websocket/demo/trip/"
    fi
fi

# Ask if user wants to start broadcast simulator
echo ""
read -p "$(echo -e ${BLUE}Do you want to start the broadcast simulator now? [y/N]:${NC} )" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}Starting broadcast simulator in background...${NC}"
    echo ""
    cd "$PROJECT_DIR"
    
    # Start broadcaster in background and get PID
    docker-compose exec -d web bash -c "uv run python manage.py test_broadcast --count 30 --interval 3"
    
    echo -e "${GREEN}✓ Broadcast simulator started${NC}"
    echo -e "${YELLOW}Broadcasting 30 updates every 3 seconds (90 seconds total)${NC}"
    echo ""
    echo -e "${BLUE}The demo page should now show real-time updates!${NC}"
    echo ""
    echo "To stop broadcasts manually:"
    echo "  docker-compose exec web pkill -f test_broadcast"
fi
