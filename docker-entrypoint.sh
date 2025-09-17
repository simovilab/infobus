#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Detect if this is a Celery service based on the command arguments
IS_CELERY=false
if [[ "$*" == *"celery"* ]]; then
    IS_CELERY=true
fi

if [ "$IS_CELERY" = true ]; then
    echo -e "${GREEN}Starting Celery service...${NC}"
    
    # Ensure virtual environment exists (install if not present)
    if [ ! -d "/app/.venv" ]; then
        echo -e "${YELLOW}Setting up virtual environment...${NC}"
        uv sync --frozen
    else
        echo -e "${GREEN}Virtual environment already exists${NC}"
    fi
    
    # Wait for database to be ready (Celery needs DB for django-celery-beat)
    echo -e "${YELLOW}Waiting for database connection...${NC}"
    until uv run python -c "import psycopg2; import os; conn = psycopg2.connect(os.environ['DATABASE_URL']); conn.close(); print('Database is ready!')"; do
        echo -e "${YELLOW}Database is unavailable - sleeping${NC}"
        sleep 2
    done
    
    echo -e "${GREEN}Database is ready! Starting Celery...${NC}"
else
    echo -e "${GREEN}Starting Django application...${NC}"

    # Ensure virtual environment exists (install if not present)
    if [ ! -d "/app/.venv" ]; then
        echo -e "${YELLOW}Setting up virtual environment...${NC}"
        uv sync --frozen
    else
        echo -e "${GREEN}Virtual environment already exists${NC}"
    fi
    
    # Wait for database to be ready
    echo -e "${YELLOW}Waiting for database connection...${NC}"
    until uv run python -c "import psycopg2; import os; conn = psycopg2.connect(os.environ['DATABASE_URL']); conn.close(); print('Database is ready!')"; do
        echo -e "${YELLOW}Database is unavailable - sleeping${NC}"
        sleep 2
    done

    echo -e "${GREEN}Database is ready!${NC}"

    # List of apps to make migrations for
    APPS_TO_MIGRATE=("website" "gtfs" "feed" "alerts" "api")

    # Make migrations for the registered apps
    echo -e "${YELLOW}Making migrations for apps...${NC}"
    uv run python manage.py makemigrations "${APPS_TO_MIGRATE[@]}" || echo -e "${YELLOW}No changes detected for migrations${NC}"

    # Run database migrations
    echo -e "${YELLOW}Running database migrations...${NC}"
    uv run python manage.py migrate --noinput

    # Create superuser if it doesn't exist
    echo -e "${YELLOW}Creating superuser if needed...${NC}"
    uv run python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Superuser created: admin/admin')
else:
    print('Superuser already exists')
" || echo -e "${YELLOW}Superuser creation skipped${NC}"

    # Collect static files
    echo -e "${YELLOW}Collecting static files...${NC}"
    uv run python manage.py collectstatic --noinput || echo -e "${YELLOW}Static files collection skipped${NC}"

    # Load initial data (if needed)
    echo -e "${YELLOW}Loading initial data...${NC}"
    uv run python manage.py loaddata bucr.json 2>/dev/null || echo -e "${YELLOW}No initial data found${NC}"

    echo -e "${GREEN}Django application setup complete!${NC}"
fi

# Execute the main command
exec "$@"