-- =============================================================
-- 003_daily_aggregates.sql
-- Materialized view of crimes aggregated by (community_area, day).
-- Forms the target variable (crime_count) for the forecasting model
-- and the base for lag/rolling features.
--
-- REFRESH on new data ingest:
--     REFRESH MATERIALIZED VIEW daily_area_counts;
-- =============================================================

-- Drop in case of re-run (idempotent).
DROP MATERIALIZED VIEW IF EXISTS daily_area_counts;

CREATE MATERIALIZED VIEW daily_area_counts AS
SELECT
    community_area,
    occurred_at::date AS day,
    COUNT(*)::integer AS crime_count
FROM crimes
WHERE community_area IS NOT NULL
GROUP BY community_area, occurred_at::date;

-- Comments for discoverability.
COMMENT ON MATERIALIZED VIEW daily_area_counts IS
    'Daily crime counts per community area. Source for forecasting model target and lag features. REFRESH after new data ingest.';

-- Indexes on the materialized view for fast lookups during feature engineering.
-- Composite (area, day) index for lag window queries ("crimes in area X, N days ago").
CREATE UNIQUE INDEX idx_dac_area_day ON daily_area_counts (community_area, day);

-- Date-only index for global time-range filters.
CREATE INDEX idx_dac_day ON daily_area_counts (day);