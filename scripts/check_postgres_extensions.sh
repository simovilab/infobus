#!/usr/bin/env bash
set -euo pipefail

# Quick integration test: start a temporary PostGIS container and try to create
# pg_trgm and unaccent extensions. Exits 0 when both can be created.

DEFAULT_LOCAL_IMAGE="infobus/postgres:16-extensions"
FALLBACK_IMAGE="postgis/postgis:16-3.4-alpine"
CONTAINER="infobus_tmp_db_check_$RANDOM"
POSTGRES_PASSWORD="postgres"
TIMEOUT=60

if docker image inspect "$DEFAULT_LOCAL_IMAGE" >/dev/null 2>&1; then
  IMAGE="$DEFAULT_LOCAL_IMAGE"
else
  IMAGE="$FALLBACK_IMAGE"
fi

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Starting temporary container from image $IMAGE..."
docker run --name "$CONTAINER" -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" -d "$IMAGE" >/dev/null

echo "Waiting for Postgres to become ready (timeout ${TIMEOUT}s)..."
for i in $(seq 1 $TIMEOUT); do
  if docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then
    echo "Postgres is ready"
    break
  fi
  sleep 1
  if [ "$i" -eq "$TIMEOUT" ]; then
    echo "Timed out waiting for Postgres. Container logs:"
    docker logs "$CONTAINER" || true
    exit 2
  fi
done

echo "Attempting to create extensions in the 'postgres' database to verify availability..."

missing=()
for ext in pg_trgm unaccent; do
  if docker exec "$CONTAINER" psql -U postgres -d postgres -c "CREATE EXTENSION IF NOT EXISTS \"${ext}\";" >/dev/null 2>&1; then
    echo "OK: Created or already present: ${ext}"
  else
    echo "ERROR: Could not create extension ${ext} (likely missing files in image)"
    missing+=("$ext")
  fi
done

if [ ${#missing[@]} -eq 0 ]; then
  echo "OK: All required extensions successfully created: pg_trgm, unaccent"
  exit 0
else
  echo "FAIL: Missing or not creatable extensions: ${missing[*]}"
  exit 3
fi
