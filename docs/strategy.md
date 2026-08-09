# Strategy Engine — Rule-Based Signals (Phase 6)

**Version:** `1.0.0`  
**Status:** Complete  
**Scope:** Deterministic BUY / SELL / WAIT / NO_TRADE for XAUUSD swing setups.

## Purpose

Consume Phase 3 (TA), Phase 4 (SMC), and Phase 5 (MTF) outputs and produce a transparent, backtestable trade **recommendation**. No ML. No broker execution. No parameter optimizer.

## Signal states

| State | Meaning |
|-------|---------|
| `BUY` | Valid bullish setup confirmed (score ≥ signal threshold + levels valid) |
| `SELL` | Valid bearish setup confirmed |
| `WAIT` | Context favorable but confirmation incomplete (score in wait band) |
| `NO_TRADE` | Invalid, conflicting, filtered, or poor RR / missing levels |

The engine never forces BUY/SELL.

## Timeframe roles

| TF | Role |
|----|------|
| 1D | Macro context |
| 4H | Primary swing structure |
| 1H | Setup timeframe |
| 15M | Entry confirmation |

Pullbacks are allowed (HTF bias may differ from entry TF briefly).

## Scoring model (research defaults)

Weights are **condition points**, not win probability.

| Condition | Weight |
|-----------|--------|
| Higher TF Bias | 20 |
| 4H Structure | 15 |
| 1H Setup | 15 |
| Liquidity Sweep | 15 |
| BOS/CHoCH | 10 |
| OB / Demand / Supply | 10 |
| FVG | 5 |
| Premium / Discount | 5 |
| 15M Confirmation | 5 |
| **Total** | **100** |

### Thresholds

| Band | Score | Outcome |
|------|-------|---------|
| Strong | ≥ 80 | Eligible BUY/SELL (if validated) |
| Valid | 65–79 | Eligible BUY/SELL |
| Wait | 50–64 | WAIT |
| Below | < 50 | NO_TRADE |

Label format: `82/100 strategy condition score` — **never** “82% probability”.

## BUY setup (conceptual)

1. 4H bullish structure + 1H bullish or pullback from bullish HTF  
2. Prefer sell-side liquidity sweep  
3. Bullish BOS or CHoCH  
4. Location: discount **or** demand/OB **or** bullish FVG  
5. 15M bullish confirmation (bias / BOS / sweep+reclaim)  
6. RR ≥ `min_rr` (default 1.5)

Incomplete → WAIT. Strong conflict / failed validation → NO_TRADE.

## SELL setup

Mirror of BUY (premium / supply / buy-side sweep / bearish breaks).

## Entry / SL / TP

### Entry zone
Prefer active OB / demand-supply / FVG bounds. Else ATR band around last closed 15M close.

Fields: `entry_low`, `entry_high`, `preferred_entry`.

### Stop loss (structural)
BUY: below sweep low / demand / OB / swing low − buffer  
SELL: above sweep high / supply / OB / swing high + buffer  

Buffer = `sl_buffer` + ATR × `sl_atr_buffer_mult`.  
No account position sizing (Risk Engine = Phase 7+).

### Take profit
Candidates: opposing liquidity, swing high/low, dealing-range extreme, nearest opposing zone.  
Compute RR1/RR2/RR3. Synthetic TP1 at `min_rr` only if no structural target exists (flagged as risk/warning).

## Filters

### MarketConditionFilter
Abstraction for news/session risk. Phase 6 defaults to `NORMAL`.  
`UNSAFE` → NO_TRADE when `reject_unsafe_market=true`. **No live news API.**

### Volatility (ATR)
`NORMAL` / `HIGH` / `EXTREME` vs median ATR.  
HIGH → score penalty. EXTREME → NO_TRADE (configurable).

## Setup / signal lifecycle

`setup_id` — stable hash of recent structure events + time bucket.  
`signal_id` — unique id; refreshed (not duplicated) for the same active setup.

Lifecycle: `DETECTED` → `CONFIRMED` → `ACTIVE` → `INVALIDATED` | `EXPIRED` | `COMPLETED`

Expiration: `max_signal_age_bars` on 15M (default 12).

## Configuration

`StrategyConfig` in `backend/app/strategy/config.py` (+ env `MIN_RR`, `STRATEGY_VERSION`).

## Causality

Signal at analysis time `as_of` uses only closed candles and events with `confirm_index` ≤ window end. Leakage tests mutate future bars and assert identical signals.

## Limitations

- Mock market data by default  
- Weights are research defaults — not optimized  
- In-memory signal history (cleared on process restart)  
- No backtest / ML / broker execution  

## Next

Phase 7 — Entry / SL / TP risk engine refinements & position sizing.
