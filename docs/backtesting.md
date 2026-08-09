# Backtesting Engine (Phase 7)

**Status:** Complete (Phase 7) · Extended in Phase 10 + 11  
**Role:** Measure strategy on historical data; optional ML filter; optional account-style risk %.  
**Non-goals:** Parameter optimizer, broker execution, model retrain during backtest.

## Question answered

> If this strategy had been run on historical data using only information available at each moment, what would performance have looked like?

## Architecture

```
Historical OHLCV
  → event loop (causal as_of)
  → Strategy / Combined signal
  → TradeSimulator (single execution path)
  → equity (FIXED_1R or RISK_PERCENT)
  → metrics
```

### Risk sizing modes (`risk_mode`) — Phase 11

| Mode | Behavior |
|------|----------|
| `FIXED_1R` (default) | 1R cash = initial_equity × risk_fraction (research normalization, no compounding) |
| `RISK_PERCENT` | 1R cash = current_equity × risk_fraction (compounds; account-style) |

Do not confuse normalized R metrics with real account P&L under `FIXED_1R`.

Same `TradeSimulator` — no second execution engine.

### Phase 10 modes (`signal_mode`)

| Mode | Behavior |
|------|----------|
| `RULE_ONLY` | Phase 6 only (default) |
| `ML_FILTER` / `COMBINED` | Phase 6 setups filtered by loaded research model |

Also: `POST /api/risk/backtest` wraps the same engine with loss-streak + research ruin estimate.

## Data

- Symbol: XAUUSD  
- TFs: 15m / 1h / 4h / 1d (HTF resampled from entry TF if missing)  
- Adapters: CSV + existing provider  
- CSV columns: `timestamp,open,high,low,close[,volume]` (volume optional → 0)  
- Timezone: UTC explicit. No hard-coded equity-session hours (Gold is extended).

## Chronological splits

TRAIN 70% / VALIDATION 15% / TEST 15% — never shuffled.  
TEST must stay untouched until strategy parameters are frozen (measurement discipline).

## Reproducibility

Each run stores `backtest_id`, `strategy_version`, `data_version`, full config. Identical inputs → identical metrics.

## Limitations

- Full strategy-per-bar is CPU heavy — use modest `limit` for interactive runs.  
- OHLC cannot resolve true intrabar path (see execution-model.md).  
- Equity uses fixed 1R = `initial_equity * risk_fraction` under `FIXED_1R` (normalization).  
- Metrics must be measured on **real** OHLCV (Phase 11.5) — synthetic mock results are not production truth.

## API

- `POST /api/backtest/run`  
- `GET /api/backtest/{id}`  
- `GET /api/backtest/{id}/trades`

## UI

Dashboard → **Backtest** page: parameters, RUN, metrics, equity curve, trades, BUY/SELL & score breakdowns.
