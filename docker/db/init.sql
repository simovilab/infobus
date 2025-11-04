-- PostgreSQL initialization script for Infobús database
-- This script runs automatically when the database is first created

-- Enable PostGIS extension (should already be enabled by postgis/postgis image, but ensure it)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable pg_trgm extension for trigram similarity searches
-- Used by the search API endpoint for fuzzy text matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Infobús database extensions initialized successfully';
    RAISE NOTICE '  - postgis: enabled';
    RAISE NOTICE '  - pg_trgm: enabled';
END $$;
