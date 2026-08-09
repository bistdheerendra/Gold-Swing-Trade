# Historical OHLCV snapshots (Phase 11.5)

CSV files written by `backend/scripts/backfill_market_data.py`:

- `{SYMBOL}_{TIMEFRAME}.csv` — e.g. `PAXGUSD_1h.csv`
- Columns: `timestamp,open,high,low,close,volume,source`

These are **real** free-tier candles (Binance / Twelve Data), not synthetic mock series.
Prefer PostgreSQL (`MARKET_DATA_STORE=postgres`) as the primary durable store; CSVs are a portable backup for ML re-runs.
