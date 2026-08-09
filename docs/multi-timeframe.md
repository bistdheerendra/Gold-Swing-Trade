# Multi-Timeframe Analysis

**Phase:** 5 (+ Phase 11.5 adds **30m**)  
**Status:** Binding specification

## Purpose

Combine independent TA + SMC analyses across `1d`, `4h`, `1h`, `30m`, `15m` into market **context** only.

This layer does **not** emit BUY / SELL / WAIT trade signals (Phase 6+).

## Timeframe hierarchy (Phase 11.5)

```
1D → 4H → 1H → 30M → 15M
```

| TF | Role |
|----|------|
| 1D | Macro trend / major context |
| 4H | Major structure / swing context |
| 1H | Primary setup context |
| **30M** | Timing / intermediate confirmation (between setup and entry) |
| 15M | Entry confirmation context |

Constant: `MTF_HIERARCHY` in `app/market/schemas.py` — do not hardcode divergent lists per module.

15M must never be interpreted in isolation in the MTF summary — it is always reported relative to HTF/setup/timing bias.

## Closed-candle synchronization (critical)

OHLCV `timestamp` is the **candle open** time (UTC).

A candle on timeframe `TF` with open `t_open` is **closed** at analysis time `as_of` if and only if:

```
t_open + TF.delta <= as_of
```

### Mapping rule

When analyzing at `as_of` (typically the close of the latest usable 15M bar, or an explicit timestamp):

1. For each timeframe independently, select the last bar whose open satisfies the closed-candle rule above.
2. Run TA and SMC with `as_of_index` equal to that bar’s index in the truncated series (`bars[:index+1]`).
3. **Never** use an unfinished higher-timeframe candle.

### Example

`as_of = 2024-06-01 13:15:00Z` (15M candle 13:00–13:15 just closed):

- 15M: last closed open = `13:00`
- 30M: last closed open = `13:00` only if that 30M slot closed; else prior open (e.g. `12:30`)
- 1H: last closed open = `12:00` (13:00 hourly candle still open until 14:00)
- 4H / 1D: same closed-candle rule as before

## No look-ahead

- No resampling that peeks into future HTF closes
- No future-confirmed swings / BOS / FVG / sweeps
- Future mutation of open HTF candles must not change past MTF snapshots

## Bias score (−100 … +100)

Configurable research weights (not proven edge):

| Factor | Default weight |
|--------|----------------|
| ema_weight | 15 |
| structure_weight | 25 |
| bos_weight | 20 |
| choch_weight | 15 |
| momentum_weight | 10 |
| liquidity_weight | 15 |

Bands:

- +70…+100 Strong Bullish
- +30…+69 Bullish
- −29…+29 Neutral
- −69…−30 Bearish
- −100…−70 Strong Bearish

Alignment scoring includes all five TFs in the hierarchy (including 30m).

## Alignment states (context only)

`TRENDING` · `PULLBACK` · `REVERSAL_RISK` · `RANGING` · `CONFLICT` · `NEUTRAL`

## API

`GET /api/mtf/analyze` (default timeframes `1d,4h,1h,30m,15m`)

See `docs/api.md`.
