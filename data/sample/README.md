# Market data notes (Phase 1)

Mock provider generates deterministic synthetic XAUUSD OHLCV for offline development.

Use the API to materialize samples:

```bash
curl -X POST "http://localhost:8000/api/market/seed?timeframe=1h&bars=300"
```

Persisted bars (when `MARKET_DATA_STORE=postgres`) live in PostgreSQL `ohlcv_bars`.
With the default `memory` store, data lives in-process for local development without Docker.
