# Risk Management — Phase 11

**Status:** COMPLETE (research / decision-support only)

## Role

Phase 11 sits **after** Phase 10 Combined Signal.

- Phase 10 → **SIGNAL** (BUY / SELL / WAIT / NO_TRADE)
- Phase 11 → **TRADE PLAN** (size, margin, costs, RR) for accepted signals only

The risk engine **never** invents BUY/SELL. WAIT stays WAIT (`SKIPPED_NO_SIGNAL`).

## Components

| Component | Path |
|-----------|------|
| InstrumentSpec / PAXGUSD | `backend/app/instruments/` |
| RiskEngine / TradePlan | `backend/app/risk/` |
| CostEngine | `backend/app/risk/costs.py` |
| Position sizing | `backend/app/risk/sizing.py` |
| Margin | `backend/app/risk/margin.py` |
| Daily / streak guards | `backend/app/risk/guards.py` |
| Read-only broker | `backend/app/risk/broker.py` |
| API | `/api/risk/*` |

## Risk model

```
risk_amount = account_balance × risk_per_trade_pct / 100
loss_per_contract = contract_size × stop_distance
raw_quantity = risk_amount_usd / loss_per_contract
quantity = floor_to_step(raw) within [min, max]
required_margin = notional / leverage
```

Leverage affects **margin only**, not the risk amount.

## Status codes

`RISK_ACCEPTED` · `RISK_REJECTED` · `INVALID` · `INSUFFICIENT_MARGIN` ·
`POSITION_LIMIT_EXCEEDED` · `DAILY_LIMIT_REACHED` · `TRADING_BLOCKED` ·
`SKIPPED_NO_SIGNAL` · …

## Non-goals

- No live orders / `place_order`
- No Delta API keys stored
- No claim of PAXGUSD or ML profitability
