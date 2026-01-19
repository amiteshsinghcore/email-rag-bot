-- ===========================================
-- PST Email RAG Bot - Database Initialization
-- ===========================================
-- This script runs automatically when PostgreSQL container starts for the first time

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For trigram-based text search

-- Create schema (optional, using public by default)
-- CREATE SCHEMA IF NOT EXISTS pstrag;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE pstrag_db TO pstrag;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully at %', NOW();
END $$;
