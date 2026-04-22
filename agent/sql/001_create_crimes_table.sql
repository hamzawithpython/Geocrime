-- =============================================================
-- 001_create_crimes_table.sql
-- Creates the main crimes table for the Chicago crime dataset.
-- Schema designed for 2020-present data (~1.5M rows).
-- =============================================================

-- Ensure PostGIS extension is loaded (idempotent).
CREATE EXTENSION IF NOT EXISTS postgis;

-- Drop existing table if recreating from scratch.
-- WARNING: This deletes all data. Comment out for production.
DROP TABLE IF EXISTS crimes;

-- Main crimes table.
CREATE TABLE crimes (
    id                   BIGINT PRIMARY KEY,
    case_number          TEXT,
    occurred_at          TIMESTAMPTZ NOT NULL,
    primary_type         TEXT NOT NULL,
    description          TEXT,
    location_description TEXT,
    arrest               BOOLEAN NOT NULL DEFAULT FALSE,
    domestic             BOOLEAN NOT NULL DEFAULT FALSE,
    community_area       SMALLINT,
    district             SMALLINT,
    geom                 GEOMETRY(POINT, 4326)
);

-- Comments for documentation (visible in psql with \d+ crimes).
COMMENT ON TABLE  crimes IS 'Chicago crime incidents from 2020 onwards. Source: Chicago Open Data Portal.';
COMMENT ON COLUMN crimes.id IS 'Stable city-assigned record ID.';
COMMENT ON COLUMN crimes.occurred_at IS 'When the incident occurred (TIMESTAMPTZ in UTC).';
COMMENT ON COLUMN crimes.primary_type IS 'Top-level crime classification (THEFT, ASSAULT, ROBBERY, etc.).';
COMMENT ON COLUMN crimes.community_area IS 'One of 77 Chicago administrative neighborhoods.';
COMMENT ON COLUMN crimes.geom IS 'Point geometry in WGS84 (SRID 4326). Use ST_X(geom) for longitude, ST_Y(geom) for latitude.';

-- =============================================================
-- Indexes
-- =============================================================

-- Spatial index for "near this point" queries.
CREATE INDEX idx_crimes_geom ON crimes USING GIST (geom);

-- Date filtering — used by every time-windowed query.
CREATE INDEX idx_crimes_occurred_at ON crimes (occurred_at);

-- Crime type filtering — common in agent queries.
CREATE INDEX idx_crimes_primary_type ON crimes (primary_type);

-- Neighborhood aggregation.
CREATE INDEX idx_crimes_community_area ON crimes (community_area);