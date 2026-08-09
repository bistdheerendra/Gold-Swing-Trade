-- Phase 1: normalized OHLCV storage

CREATE TABLE IF NOT EXISTS ohlcv_bars (
    id BIGSERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    open NUMERIC(18, 6) NOT NULL,
    high NUMERIC(18, 6) NOT NULL,
    low NUMERIC(18, 6) NOT NULL,
    close NUMERIC(18, 6) NOT NULL,
    volume NUMERIC(18, 6) NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'unknown',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_ohlcv_symbol_tf_ts UNIQUE (symbol, timeframe, timestamp),
    CONSTRAINT ck_ohlcv_high_low CHECK (high >= low),
    CONSTRAINT ck_ohlcv_timeframe CHECK (timeframe IN ('15m', '1h', '4h', '1d'))
);

CREATE INDEX IF NOT EXISTS ix_ohlcv_symbol_tf_ts
    ON ohlcv_bars (symbol, timeframe, timestamp);

INSERT INTO schema_meta (key, value)
VALUES ('phase', '1')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
