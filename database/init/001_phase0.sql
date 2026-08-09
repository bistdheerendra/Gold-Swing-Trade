-- Phase 0 bootstrap schema placeholders
-- Full OHLCV / signal tables arrive in Phase 1+

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO schema_meta (key, value)
VALUES ('phase', '0'), ('app', 'Gold Swing AI')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
