# Performance Metrics (Phase 7)

All trade performance is primarily in **R-multiples** (risk units).

## R definition

```
risk = |entry − stop_loss|
R = (exit − entry) / risk   # BUY
R = (entry − exit) / risk   # SELL
```

SL hit ≈ −1R (before costs). Costs reduce **net R**.

## Equity normalization (not Risk Engine)

```
1R cash = initial_equity × risk_fraction   # default 1%
equity += net_r × 1R_cash
```

Fixed against **initial** equity (non-compounding normalization). Phase 11 owns real position sizing.

## Reported metrics

- Signals / expired / entered  
- Wins / losses / breakeven  
- Win rate  
- Gross / net profit in R  
- Average win / loss / R  
- Expectancy (R)  
- Profit factor  
- Max drawdown (cash + %) + start/end when available  
- Streaks  
- Average duration (bars)  
- Total trading cost  

## Breakdowns (report only — no optimizer)

- BUY vs SELL  
- Score buckets: 50–64, 65–74, 75–84, 85–100  
- Market state: TRENDING / PULLBACK / …  
- Hour / day-of-week / month  

## Forbidden in Phase 7

Parameter search, weight tuning, RR optimization, picking the best window after peeking at results.
