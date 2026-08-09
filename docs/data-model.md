# Data Model — Gold Swing AI

**Phase:** 1  
Concrete ORM model: `backend/app/models/ohlcv.py`  
SQL: `database/init/002_ohlcv.sql`

## Design rules

1. Normalize OHLCV once; all consumers read the same schema.
2. Never embed broker-specific fields into strategy tables.
3. Store strategy version and model version on every signal/trade.
4. Timestamps are UTC.

## Core entities

### `ohlcv_bars` (Phase 1 — implemented)

| Column | Type | Notes |
|--------|------|-------|
| id | BIGSERIAL | PK |
| symbol | TEXT | e.g. XAUUSD |
| timeframe | TEXT | 15m, 1h, 4h, 1d |
| timestamp | TIMESTAMPTZ | candle open time (UTC) |
| open | NUMERIC(18,6) | |
| high | NUMERIC(18,6) | |
| low | NUMERIC(18,6) | |
| close | NUMERIC(18,6) | |
| volume | NUMERIC(18,6) | |
| source | TEXT | provider id (`mock`, …) |
| created_at | TIMESTAMPTZ | insert time |

Unique: `(symbol, timeframe, timestamp)`

### `smc_events` (Phase 4)

| Column | Notes |
|--------|-------|
| type | bullish_fvg, bos, order_block, … |
| timeframe | |
| timestamp | |
| high / low | price range |
| direction | |
| strength | |
| valid | boolean |
| source_indexes | candle indexes |

### `signals` (Phase 6+)

| Column | Notes |
|--------|-------|
| timestamp | |
| symbol / timeframe | |
| direction | BUY / SELL / WAIT / NO_TRADE |
| entry / sl / tp1 / tp2 | |
| ml_probability | |
| confidence | |
| reason / risks | JSON or text |
| strategy_version | |
| model_version | |
| result / pnl | filled later |

### `backtest_trades` (Phase 8)

Stores every simulated trade with costs, slippage, and equity impact.

### `schema_meta`

Bootstrap key/value table. Phase marker updated to `1` by `002_ohlcv.sql`.

## Validation invariants (OHLCV) — implemented

- Chronological order
- No duplicate timestamps per symbol/timeframe
- `high >= max(open, close)` and `low <= min(open, close)`
- Consistent timezone (UTC)
- Detect missing candles relative to timeframe grid (report only; do not fabricate)

See [market-data.md](market-data.md).
