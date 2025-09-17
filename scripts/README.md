# Infobus Scripts

This directory contains convenience scripts to manage the Infobus application in different environments.

## Scripts

### `dev.sh` - Development Environment

Starts the Infobus application in development mode with:
- Live code reloading
- Debug mode enabled
- Volume mounting for instant changes
- Django development server (Daphne)
- Hot reload with watchdog

**Usage:**
```bash
./scripts/dev.sh
```

**Prerequisites:**
- `.env` file with base configuration
- `.env.dev` file (auto-created if missing)
- `.env.local` file (auto-created from example if missing)

**Services started:**
- Web application: http://localhost:8000
- Database: localhost:5432 (postgres/postgres)
- Redis: localhost:6379

### `prod.sh` - Production Environment

Starts the Infobus application in production mode with:
- Nginx reverse proxy
- Security headers and rate limiting
- Static file caching
- PostGIS database support
- Celery workers and beat scheduler
- Production optimizations

**Usage:**
```bash
./scripts/prod.sh
```

**Prerequisites:**
- `.env.prod` file with production settings
- `docker-compose.production.yml` file
- `nginx/` directory with configuration

**Services started:**
- Web application: http://localhost (Nginx)
- Database: localhost:5432
- Redis: localhost:6379

## Common Commands

### Development
```bash
# Start development environment
./scripts/dev.sh

# View logs
docker-compose logs -f

# Stop development environment
docker-compose down

# Run Django shell
docker-compose exec web uv run python manage.py shell

# Run migrations
docker-compose exec web uv run python manage.py migrate
```

### Production
```bash
# Start production environment
./scripts/prod.sh

# View production logs
docker-compose -f docker-compose.production.yml logs -f

# Stop production environment
docker-compose -f docker-compose.production.yml down

# Run production Django shell
docker-compose -f docker-compose.production.yml exec web uv run python manage.py shell
```

## File Structure

```
scripts/
├── README.md          # This documentation
├── dev.sh            # Development startup script
└── prod.sh           # Production startup script
```

## Environment Files

- `.env` - Base configuration (shared)
- `.env.dev` - Development overrides
- `.env.local` - Local development secrets (git-ignored)
- `.env.prod` - Production configuration

## Script Features

Both scripts include:
- **Color-coded output** for better readability
- **Error checking** and validation
- **Health checks** after startup
- **Helpful command suggestions**
- **Automatic file creation** for missing configurations
- **Service status verification**

## Troubleshooting

1. **Permission denied**: Run `chmod +x scripts/*.sh`
2. **Missing files**: Scripts will auto-create basic configurations
3. **Port conflicts**: Stop existing services with `docker-compose down`
4. **Database issues**: Check if PostgreSQL is running in another process