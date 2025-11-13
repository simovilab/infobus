-- PostgreSQL initialization script for Infobús database
-- This script runs automatically when the database is first created

-- Enable PostGIS extension (should already be enabled by postgis/postgis image, but ensure it)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Enable pg_trgm extension for trigram similarity searches
-- Used by the search API endpoint for fuzzy text matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable unaccent extension for accent-insensitive text matching
-- Enables multilingual search (Spanish, Portuguese, etc.)
-- Searches like 'San José' will match 'San Jose' and vice versa
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Infobús database extensions initialized successfully';
    RAISE NOTICE '  - postgis: enabled';
    RAISE NOTICE '  - pg_trgm: enabled (fuzzy text matching)';
    RAISE NOTICE '  - unaccent: enabled (accent-insensitive search)';
END $$;
