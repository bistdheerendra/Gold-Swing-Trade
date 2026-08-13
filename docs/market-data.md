# Market Data Engine

**Status:** Phase 11.12 — Delta India multi-instrument (PAXGUSD + SLVONUSD)  
**Rule:** Never silently fall back to mock/synthetic data on API failure.  
**Rule:** Never blend PAXGUSD and SLVONUSD series, signals, or backtest stats.

## Pipeline

```
RealMarketDataProvider (delta_india | twelvedata)
  → OHLCVValidator (causal / OHLC / gap checks)
  → MarketDataRepository (memory | postgres)  # keyed by symbol+timeframe
  → API / UI / backtest / ML
```

## Providers

| Env value | Class | Use |
|-----------|--------|-----|
| `delta_india` (**default**) | `RealMarketDataProvider(provider="delta_india")` | Authoritative **PAXGUSD** + **SLVONUSD** candles from Delta Exchange India — **no API key** |
| `twelvedata` | `RealMarketDataProvider(provider="twelvedata")` | Optional legacy **XAU/USD** research reference — free API key required |
| `mock` | `MockMarketDataProvider` | **Pytest only** — requires `ALLOW_MOCK_DATA=true` |

### Symbol coverage

| App symbol | Provider | Notes |
|------------|----------|-------|
| **PAXGUSD** | Delta India `GET /v2/history/candles` | Symbol string **verified** against `GET /v2/products` (listed as `PAXGUSD`, perpetual, live) |
| **SLVONUSD** | Delta India `GET /v2/history/candles` | Verified Phase 11.12 — iShares Silver (XAG) Trust ONDO Token perpetual; **independent** of PAXGUSD |
| **XAUUSD** | Twelve Data `XAU/USD` | Legacy reference only — **not** in primary UI tabs; do not blend with Delta |

Do **not** use Binance `PAXGUSDT` as a PAXGUSD proxy — Delta India is the trading venue source of truth.

## SLVONUSD contract spec (Delta India `/v2/products`)

Verified live product row (Phase 11.12):

| Field | Value | Source |
|-------|-------|--------|
| symbol | `SLVONUSD` | products API |
| contract_type | `perpetual_futures` | products API |
| state | `live` | products API |
| contract_value | `0.1` SLVON per contract | products API |
| tick_size | `0.01` | products API |
| maker / taker fee | `0.0001` (0.01%) | products API |
| position_size_limit | `62000` | products API |
| default_leverage | `50` | products API (research default stays **5×**) |
| funding interval | `28800` s (8h) | `product_specs.rate_exchange_interval` |
| tags | metal / tradfi | product_specs |

Registered in `backend/app/instruments/slvonusd.py` — **do not reuse PAXGUSD’s** `contract_value=0.001` or 4h funding.

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
| `DELTA_PAXGUSD_SYMBOL` | `PAXGUSD` | Confirmed via `/v2/products` |
| `DELTA_SLVONUSD_SYMBOL` | `SLVONUSD` | Confirmed via `/v2/products` |
| `TWELVEDATA_API_BASE_URL` | `https://api.twelvedata.com` | |
| `TWELVEDATA_API_KEY` | _(empty)_ | Free key if using legacy XAUUSD |
| `MARKET_DATA_STORE` | `memory` | Prefer `postgres` for durable ML/backtest datasets |
| `MARKET_SYMBOL` | `PAXGUSD` | |

### Delta India (no key)

Public market/candle endpoints require **no** API key. Order placement APIs (not used) would need auth.

Product verification runs against `GET /v2/products` **per symbol** before candle pulls.

## Historical backfill

```bash
cd backend
# Both Delta instruments (separate CSV files)
python scripts/backfill_market_data.py --symbols PAXGUSD,SLVONUSD --timeframes "15m,30m,1h,4h,1d"

# Silver only
python scripts/backfill_market_data.py --symbols SLVONUSD --timeframes "15m,30m,1h,4h,1d"

# or
curl -X POST http://127.0.0.1:8000/api/market/backfill \
  -H "Content-Type: application/json" \
  -d '{"symbols":["SLVONUSD"],"timeframes":["15m","30m","1h","4h","1d"]}'
```

CSV snapshots: `data/historical/{SYMBOL}_{TF}.csv`  
Examples: `PAXGUSD_1h.csv`, `SLVONUSD_1h.csv` — **never overwrite one with the other**.

Prefer `MARKET_DATA_STORE=postgres`.

## Failure behavior

- Provider HTTP / parse / validation failures **raise loudly**  
- `/api/market/status` exposes `provider_ok` + `last_error` + `verified_delta_symbols`  
- **No** automatic switch to mock data

## API

- `GET /api/market/status`  
- `GET /api/market/ohlcv`  
- `POST /api/market/ingest`  
- `POST /api/market/backfill`  
- `POST /api/market/seed` / `refresh`  
- `GET /api/market/ticker` — Delta live ticker when `delta_india` (pass `?symbol=SLVONUSD`)
