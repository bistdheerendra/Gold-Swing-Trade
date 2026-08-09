# Market Data Engine

**Status:** Phase 11.5 — Real free-tier providers (Delta India primary + Twelve Data optional)  
**Rule:** Never silently fall back to mock/synthetic data on API failure.

## Pipeline

```
RealMarketDataProvider (delta_india | twelvedata)
  → OHLCVValidator (causal / OHLC / gap checks)
  → MarketDataRepository (memory | postgres)
  → API / UI / backtest / ML
```

## Providers

| Env value | Class | Use |
|-----------|--------|-----|
| `delta_india` (**default**) | `RealMarketDataProvider(provider="delta_india")` | Authoritative **PAXGUSD** candles from Delta Exchange India — **no API key** |
| `twelvedata` | `RealMarketDataProvider(provider="twelvedata")` | Optional **XAU/USD** research reference — free API key required |
| `mock` | `MockMarketDataProvider` | **Pytest only** — requires `ALLOW_MOCK_DATA=true` |

### Symbol coverage

| App symbol | Provider | Notes |
|------------|----------|-------|
| **PAXGUSD** | Delta India `GET /v2/history/candles` | Symbol string **verified** against `GET /v2/products` (listed as `PAXGUSD`, perpetual, live) |
| **XAUUSD** | Twelve Data `XAU/USD` | Reference only — **do not blend** with Delta PAXGUSD series |

Do **not** use Binance `PAXGUSDT` as a PAXGUSD proxy — Delta India is the trading venue source of truth.

## Supported timeframes

`15m` · `30m` · `1h` · `4h` · `1d`  
(Single source of truth: `Timeframe` enum / `SUPPORTED_TIMEFRAMES` / `MTF_HIERARCHY`)

Delta India natively supports `resolution=30m` — no resampling.

## Configuration

| Env | Default | Notes |
|-----|---------|-------|
| `MARKET_DATA_PROVIDER` | `delta_india` | `delta_india` \| `twelvedata` \| `mock` |
| `ALLOW_MOCK_DATA` | `false` | Must be `true` for pytest mock path only |
| `DELTA_INDIA_BASE_URL` | `https://api.india.delta.exchange` | Public REST root |
| `DELTA_PAXGUSD_SYMBOL` | `PAXGUSD` | Confirmed via `/v2/products` — do not assume blindly |
| `TWELVEDATA_API_BASE_URL` | `https://api.twelvedata.com` | |
| `TWELVEDATA_API_KEY` | _(empty)_ | Free key at [twelvedata.com](https://twelvedata.com) if using XAUUSD |
| `MARKET_DATA_STORE` | `memory` | Prefer `postgres` for durable ML/backtest datasets |
| `MARKET_SYMBOL` | `PAXGUSD` | |

### Delta India (no key)

Public market/candle endpoints require **no** API key. Order placement APIs (not used) would need auth.

Product verification runs against `GET /v2/products` before candle pulls.

### Twelve Data free key (optional XAUUSD)

1. Create a free account at https://twelvedata.com  
2. Set `TWELVEDATA_API_KEY=...`  
3. Set `MARKET_DATA_PROVIDER=twelvedata` for XAUUSD reference pulls  
4. Free tier ≈ **800 requests/day** — backfill uses exponential backoff on 429

## Historical backfill

```bash
cd backend
python scripts/backfill_market_data.py --symbols PAXGUSD --timeframes "15m,30m,1h,4h,1d"
# or
curl -X POST http://127.0.0.1:8000/api/market/backfill \
  -H "Content-Type: application/json" \
  -d '{"symbols":["PAXGUSD"],"timeframes":["15m","30m","1h","4h","1d"]}'
```

CSV snapshots: `data/historical/{SYMBOL}_{TF}.csv`. Prefer `MARKET_DATA_STORE=postgres`.

## Failure behavior

- Provider HTTP / parse / validation failures **raise loudly**  
- `/api/market/status` exposes `provider_ok` + `last_error`  
- **No** automatic switch to mock data

## API

- `GET /api/market/status`  
- `GET /api/market/ohlcv`  
- `POST /api/market/ingest`  
- `POST /api/market/backfill`  
- `POST /api/market/seed` / `refresh`  
- `GET /api/market/ticker` — Delta live ticker when `delta_india`
