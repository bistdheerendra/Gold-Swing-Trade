# Execution Model (Phase 7)

## Entry

Signal provides `entry_low`, `entry_high`, `preferred_entry`.

Zone intersection (BUY and SELL):

```
bar.low <= entry_high AND bar.high >= entry_low
```

Fill price:

1. Intersection of entry zone ∩ candle range  
2. Prefer `preferred_entry` if inside intersection  
3. Else clamp preferred into intersection  
4. Apply adverse half-spread + slippage  

**Do not** assume preferred was filled if price never traded there.

## Stop / targets

Before opening:

- BUY: SL < entry < TP  
- SELL: TP < entry < SL  

Invalid → CANCELLED (not a loss).

## TP modes

`FULL_AT_TP1` (default), `TP1_THEN_RUNNER` (Phase 7 exits at TP1), `TP2`, `TP3`.

No complex partial position sizing (Risk Engine later).

## Same-candle ambiguity

If one candle touches both SL and TP, OHLC cannot prove order.

| Policy | Behavior |
|--------|----------|
| `CONSERVATIVE` (default) | Assume **SL first** |
| `SKIP` | Do not resolve; mark `AMBIGUOUS_SKIP` (excluded from R metrics) |

## Lifecycle

`SIGNAL → PENDING → ENTERED/ACTIVE → TP_HIT | SL_HIT | EXPIRED | CANCELLED`

Pending past `max_signal_age_bars` → EXPIRED (not a losing trade).

## Costs

Applied in the backtester only (`BacktestCostConfig`):

- `spread_points`  
- `slippage_points`  
- `commission_per_trade`  

Modes: `ZERO_COST` | `REALISTIC_COST` (default realistic non-zero spread/slip).

Results expose gross R, trading cost, net R.
