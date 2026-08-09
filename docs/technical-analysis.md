# Technical Analysis Engine

**Phase:** 3  
**Status:** Implemented

## Purpose

Deterministic, causal indicator + market-structure calculations for XAUUSD OHLCV.

UI must not invent indicator math for trading decisions. Chart EMA overlays (Phase 2) are display helpers; this engine is the source of truth for strategy/ML later.

## Indicators

| Group | Indicator | Notes |
|-------|-----------|-------|
| Trend | EMA 20/50/100/200 | SMA seed, then recursive EMA |
| Momentum | RSI (14) | Wilder |
| Momentum | MACD (12/26/9) | Line, signal, histogram |
| Momentum | ADX / +DI / -DI (14) | Wilder |
| Volatility | ATR (14) | Wilder |
| Volatility | Bollinger (20, 2σ) | Population std of trailing window |
| Structure | Swing High / Low | Fractal left/right |
| Structure | HH / HL / LH / LL | Labeled vs prior same-type swing |

## Look-ahead rules

1. Indicator value at index `i` uses only bars `0..i`.
2. Engine `analyze(..., as_of_index=k)` truncates input to `bars[:k+1]` before any math.
3. Swing pivots require `right` future bars for confirmation, but are **emitted only at `confirm_index = pivot + right`**. Features at time `t` include only swings with `confirm_index <= t`.
4. Tests assert extending future bars does not rewrite past confirmed swings / EMA values.

## API

`GET /api/ta/analyze?timeframe=1h&limit=500`

Optional: `as_of_index`, `swing_left`, `swing_right`.

Returns latest values, full series arrays, and structure snapshot.

## Modules

| Path | Role |
|------|------|
| `backend/app/ta/indicators.py` | Pure indicator functions |
| `backend/app/ta/structure.py` | Swings + HH/HL/LH/LL |
| `backend/app/ta/engine.py` | Orchestration |
| `backend/app/api/ta.py` | HTTP API |

## Not in Phase 3

- SMC (BOS, FVG, OB, liquidity) — Phase 4
- Multi-timeframe bias aggregation — Phase 5
- Signal generation — Phase 6
- RSI/MACD chart panes (optional later UI)
