-- =============================================================
-- 002_add_geog_column.sql
-- Adds a stored geography column (geog) derived from geom, plus
-- a GIST index on it. Enables spatial index usage for
-- meter-based distance queries (ST_DWithin with 500m, etc.).
-- =============================================================

-- Drop in case of re-run (idempotent).
DROP INDEX IF EXISTS idx_crimes_geog;
ALTER TABLE crimes DROP COLUMN IF EXISTS geog;

-- Add the generated geography column.
-- STORED means it's computed at write-time and saved (vs VIRTUAL which
-- computes at read-time and can't be indexed).
ALTER TABLE crimes
    ADD COLUMN geog GEOGRAPHY(POINT, 4326)
    GENERATED ALWAYS AS (geom::geography) STORED;

COMMENT ON COLUMN crimes.geog IS
    'Geography type (sphere-based) derived from geom. Use for meter-based ST_DWithin queries.';

-- Spatial index on the new column.
CREATE INDEX idx_crimes_geog ON crimes USING GIST (geog);