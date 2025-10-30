-- Docker init script to create useful PostgreSQL extensions
-- This file will be executed by the official Postgres entrypoint on first initialization

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
