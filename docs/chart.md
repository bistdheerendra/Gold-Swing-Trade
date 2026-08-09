# Market Chart

**Phase:** 2  
**Status:** Implemented

## Purpose

Render reusable XAUUSD candlestick charts fed by the Phase 1 market data API.

## Features

- Candlestick series (TradingView Lightweight Charts v4)
- Timeframe selector: `15m` / `1h` / `4h` / `1d`
- Zoom (scroll) + pan (drag)
- Crosshair with live OHLC banner
- EMA overlays: 20 / 50 / 100 / 200 (toggleable)
- Auto-seed mock bars when the store is empty

## Components

| File | Role |
|------|------|
| `frontend/src/components/charts/CandlestickChart.tsx` | Reusable chart + OHLC banner |
| `frontend/src/components/charts/EmaToggleBar.tsx` | EMA visibility toggles |
| `frontend/src/components/TimeframeSelector.tsx` | Timeframe control |
| `frontend/src/lib/ema.ts` | Causal EMA (no look-ahead) |
| `frontend/src/lib/chartData.ts` | OHLCV → chart adapters |
| `frontend/src/lib/api.ts` | `loadChartBars` / seed helpers |

## Look-ahead controls

EMA at index `i` uses only `closes[0..i]`. Warm-up bars before the period are omitted from the line series. Extending the series does not rewrite past EMA values (covered by tests).

## Not in Phase 2

- RSI / ATR / MACD / ADX (Phase 3 TA engine)
- SMC overlays rendering (Phase 4)
- Server-side indicator persistence
