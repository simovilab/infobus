#!/bin/bash
set -euo pipefail

# Virtual environment paths
VENV_DIR="${UV_PROJECT_ENVIRONMENT:-/home/app/.venv}"
UV_SYNC_LOCKDIR="/app/.uv-sync.lockdir"
CLONE_IO_LOCKDIR="/app/.gtfs-io-clone.lockdir"
CLONE_LOCKDIR="/app/.gtfs-django-clone.lockdir"
DUCKDB_CLI_DIR="/home/app/.duckdb/cli/latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log(){ echo -e "${GREEN}[entrypoint]${NC} $*"; }
warn(){ echo -e "${YELLOW}[entrypoint][warn]${NC} $*"; }
err(){ echo -e "${RED}[entrypoint][error]${NC} $*"; }

section(){
    log ">>> $1"
}

is_true(){
    case "${1:-}" in
        1|true|TRUE|True|yes|YES|on|ON) return 0 ;;
        *) return 1 ;;
    esac
}

clone_gtfs_io() {
    if [ -d "gtfs-io/.git" ]; then
        log "gtfs-io directory already present; skipping clone"
        return
    fi

    warn "gtfs-io not found; waiting for clone lock"
    while ! mkdir "${CLONE_IO_LOCKDIR}" 2>/dev/null; do
        if [ -d "gtfs-io/.git" ]; then
            log "gtfs-io is now available"
            return
        fi
        sleep 1
    done

    cleanup_io_clone_lock() {
        rmdir "${CLONE_IO_LOCKDIR}" 2>/dev/null || true
    }

    trap cleanup_io_clone_lock EXIT

    if [ -d "gtfs-io/.git" ]; then
        log "gtfs-io already cloned"
        cleanup_io_clone_lock
        trap - EXIT
        return
    fi

    log "Cloning gtfs-io repository..."
    git clone https://github.com/simovilab/gtfs-io.git gtfs-io

    log "gtfs-io cloned"
    cleanup_io_clone_lock
    trap - EXIT
}

clone_gtfs_django() {
    if [ -d "gtfs-django/.git" ]; then
        log "gtfs-django directory already present; skipping clone"
        return
    fi

    warn "gtfs-django not found; waiting for clone lock"
    while ! mkdir "${CLONE_LOCKDIR}" 2>/dev/null; do
        if [ -d "gtfs-django/.git" ]; then
            log "gtfs-django is now available"
            return
        fi
        sleep 1
    done

    cleanup_clone_lock() {
        rmdir "${CLONE_LOCKDIR}" 2>/dev/null || true
    }

    trap cleanup_clone_lock EXIT

    if [ -d "gtfs-django/.git" ]; then
        log "gtfs-django already cloned"
        cleanup_clone_lock
        trap - EXIT
        return
    fi

    log "Cloning gtfs-django repository..."
    git clone https://github.com/simovilab/gtfs-django.git gtfs-django

    log "gtfs-django cloned"
    cleanup_clone_lock
    trap - EXIT
}

# ------------------------------------------------
section "Building DATABASE_URL from components..."
# ------------------------------------------------

if [ -z "${DATABASE_URL:-}" ]; then
    if [[ -n "${DB_USER:-}" && -n "${DB_HOST:-}" && -n "${DB_NAME:-}" ]]; then
        if [ -n "${DB_PASSWORD:-}" ]; then
            export DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME}"
        else
            export DATABASE_URL="postgresql://${DB_USER}@${DB_HOST}:${DB_PORT:-5432}/${DB_NAME}"
        fi
        warn "DATABASE_URL not set; using DB_* variables (user='${DB_USER}', host='${DB_HOST}', db='${DB_NAME}', port='${DB_PORT:-5432}')"
    else
        warn "DATABASE_URL not set and insufficient components to construct it."
    fi
fi

# ----------------------------------------------
section "Cloning gtfs-io (workspace member)..."
# ----------------------------------------------

clone_gtfs_io

# ----------------------------------------------
section "Cloning gtfs-django (workspace member)..."
# ----------------------------------------------

clone_gtfs_django

# ----------------------------------------------
section "Enabling Python virtual environment..."
# ----------------------------------------------

setup_virtualenv() {
    # Fast path: if another container already prepared the venv, reuse it.
    if [ -d "${VENV_DIR}/bin" ]; then
        log "Virtual environment already exists"
        return
    fi

    # Only one container should run `uv sync` at a time when /app is shared.
    # Wait until we can create the lock directory, or exit early if the venv
    # appears while we are waiting.
    warn "Virtual environment not found; waiting for setup lock"
    while ! mkdir "${UV_SYNC_LOCKDIR}" 2>/dev/null; do
        if [ -d "${VENV_DIR}/bin" ]; then
            log "Virtual environment is now available"
            return
        fi
        sleep 1
    done

    cleanup_lock() {
        rmdir "${UV_SYNC_LOCKDIR}" 2>/dev/null || true
    }

    # Always release the lock on exit/error so other containers are not blocked.
    trap cleanup_lock EXIT

    # Race check: another container may have finished setup right before we
    # acquired the lock.
    if [ -d "${VENV_DIR}/bin" ]; then
        log "Virtual environment already exists"
        cleanup_lock
        trap - EXIT
        return
    fi

    # Build the virtual environment with retries to survive transient failures.
    # If setup fails repeatedly, stop the container to make the issue visible.
    warn "Setting up virtual environment (uv sync)..."
    attempts=0
    until uv sync --frozen; do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge 3 ]; then
            err "uv sync failed after ${attempts} attempts"
            exit 1
        fi
        warn "uv sync failed (attempt ${attempts}/3); cleaning partial env and retrying"
        rm -rf "${VENV_DIR}" || true
        sleep 2
    done

    # Setup succeeded; explicitly release lock and clear trap.
    log "Virtual environment ready"
    cleanup_lock
    trap - EXIT
}

setup_virtualenv

if [ -d "${VENV_DIR}/bin" ]; then
    export PATH="${VENV_DIR}/bin:$PATH"
fi

install_duckdb_cli() {
    if [ -x "${DUCKDB_CLI_DIR}/duckdb" ]; then
        log "DuckDB CLI already installed"
    else
        if ! command -v curl >/dev/null 2>&1; then
            warn "curl not found; skipping DuckDB CLI installation"
            return
        fi

        mkdir -p "${DUCKDB_CLI_DIR}"
        duckdb_version="v1.5.3"

        case "$(uname -m)" in
            x86_64)
                duckdb_asset="duckdb_cli-linux-amd64.zip"
                duckdb_sha256="35caef1fecbc8d7e2c07de4fd2cdefc5189ec9ba9e1cca228fb1a1c48cc52a8a"
                ;;
            aarch64|arm64)
                duckdb_asset="duckdb_cli-linux-arm64.zip"
                duckdb_sha256="5e2399428793642e994f1584c47d49f4c58b7b4ec2297ea4a522353a6c553835"
                ;;
            *)
                warn "Unsupported architecture for DuckDB CLI: $(uname -m)"
                return
                ;;
        esac

        duckdb_url="https://github.com/duckdb/duckdb/releases/download/${duckdb_version}/${duckdb_asset}"
        temp_dir="$(mktemp -d)"
        zip_path="${temp_dir}/duckdb.zip"

        warn "Installing DuckDB CLI ${duckdb_version} from pinned artifact..."
        attempts=0
        until curl -fsSL -o "${zip_path}" "${duckdb_url}"; do
            attempts=$((attempts + 1))
            if [ "$attempts" -ge 3 ]; then
                err "DuckDB CLI download failed after ${attempts} attempts"
                rm -rf "${temp_dir}"
                return
            fi
            warn "DuckDB CLI download failed (attempt ${attempts}/3); retrying"
            sleep 2
        done

        actual_sha256="$(sha256sum "${zip_path}" | awk '{print $1}')"
        if [ "${actual_sha256}" != "${duckdb_sha256}" ]; then
            err "DuckDB CLI checksum verification failed"
            rm -rf "${temp_dir}"
            return
        fi

        if ! python - "${zip_path}" "${DUCKDB_CLI_DIR}" <<'PY'
import sys
import zipfile

zip_path = sys.argv[1]
destination_dir = sys.argv[2]

with zipfile.ZipFile(zip_path, "r") as zip_ref:
    zip_ref.extract("duckdb", destination_dir)
PY
        then
            err "DuckDB CLI extraction failed"
            rm -rf "${temp_dir}"
            return
        fi

        chmod +x "${DUCKDB_CLI_DIR}/duckdb"
        rm -rf "${temp_dir}"
        log "DuckDB CLI installation complete"
    fi

    if [ -d "${DUCKDB_CLI_DIR}" ]; then
        export PATH="${DUCKDB_CLI_DIR}:$PATH"
        log "DuckDB CLI added to PATH (${DUCKDB_CLI_DIR})"
    else
        warn "DuckDB CLI directory not found at ${DUCKDB_CLI_DIR}"
    fi
}

# ------------------------------------------
section "Installing DuckDB CLI (if needed)..."
# ------------------------------------------

if [ "${1:-}" = "orchestrator" ]; then
    install_duckdb_cli
else
    log "Skipping DuckDB CLI install for service '${1:-unknown}'"
fi

# In dev mode, replace the PyPI-installed gtfs-django with an editable install
# pointing at a local clone. This requires UV_NO_SYNC=1 in the container env so
# subsequent `uv run` calls don't revert the editable install back to PyPI.
# Note: toggling GTFS_DJANGO_DEV between runs requires removing the backend_venv
# volume, otherwise setup_virtualenv's fast path skips uv sync and the previous
# mode's install sticks around.
enable_local_gtfs_io() {
    log "Enabling local editable install of gtfs-io..."
    uv add --editable ./gtfs-io
}

enable_local_gtfs_django() {
    # clone_gtfs_django() already ran before uv sync; directory is guaranteed present.
    log "gtfs-django workspace member active (editable via pyproject.toml)"
}

wait_for_database() {
    # Explicitly fail if DATABASE_URL is still missing after construction step.
    if [ -z "${DATABASE_URL:-}" ]; then
        err "DATABASE_URL is required to continue. Set DATABASE_URL or DB_USER/DB_HOST/DB_NAME."
        exit 1
    fi

    until uv run python -c "import os, psycopg2; conn = psycopg2.connect(os.environ['DATABASE_URL']); conn.close(); print('Database is ready!')"; do
        warn "Database is unavailable - sleeping"
        sleep 5
    done
}

run_makemigrations() {
    if is_true "${DEBUG:-False}"; then
        APPS_TO_MIGRATE=("feed" "engine")
        log "Creating migrations for: ${APPS_TO_MIGRATE[*]}"
        uv run python manage.py makemigrations "${APPS_TO_MIGRATE[@]}" || warn "No changes detected for migrations"
    else
        log "Skipping makemigrations outside DEBUG (DEBUG=${DEBUG:-})"
    fi
}

run_migrate() {
    log "Running database migrations..."
    uv run python manage.py migrate --noinput
}

ensure_dev_superuser() {
    if is_true "${DEBUG:-False}"; then
        export DJANGO_SUPERUSER_USERNAME="${DJANGO_SUPERUSER_USERNAME:-admin}"
        export DJANGO_SUPERUSER_PASSWORD="${DJANGO_SUPERUSER_PASSWORD:-admin}"
        export DJANGO_SUPERUSER_EMAIL="${DJANGO_SUPERUSER_EMAIL:-admin@example.com}"
        log "Ensuring development superuser '${DJANGO_SUPERUSER_USERNAME}' exists (DEBUG mode)"
        set +e
        uv run python manage.py createsuperuser --noinput
        csu_exit=$?
        set -e
        if [ $csu_exit -eq 0 ]; then
            log "Superuser created: ${DJANGO_SUPERUSER_USERNAME}"
        else
            warn "Superuser creation skipped (maybe already exists)"
        fi
    else
        log "Skipping auto superuser creation (DEBUG=${DEBUG:-})"
    fi
}

collect_static_files() {
    uv run python manage.py collectstatic --noinput || warn "Static files collection skipped"
}

load_initial_data() {
    if [ -f feed/fixtures/gtfs.json ]; then
        log "Loading initial data fixture gtfs.json"
        uv run python manage.py loaddata gtfs.json || warn "Initial data load failed"
    else
        log "No optional initial data fixture gtfs.json present"
    fi
}

run_django_setup() {
    section "Starting Django setup..."

    section "Enabling local gtfs-io package for development..."
    enable_local_gtfs_io

    section "Enabling local gtfs-django package for development..."
    enable_local_gtfs_django

    section "Running makemigrations (DEBUG only)..."
    run_makemigrations

    section "Running migrate..."
    run_migrate

    section "Creating superuser (DEBUG only)..."
    ensure_dev_superuser

    section "Collecting static files..."
    collect_static_files

    section "Loading initial data (if present)..."
    load_initial_data

    section "Django application setup complete!"
}

# ------------------------------------------
section "Waiting for database connection..."
# ------------------------------------------

wait_for_database
log "Database is ready!"

if is_true "${DJANGO_SETUP:-False}"; then
    run_django_setup
else
    log "Skipping Django setup (DJANGO_SETUP=${DJANGO_SETUP:-False})"
fi

# Execute the main command
log "Launching: $*"
exec "$@"