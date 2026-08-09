# Architecture — Gold Swing AI

**Phase:** 11 complete · **Next:** 12 (Paper Trading + Live Monitoring)  
**Last updated:** 2026-08-08

## Pipeline

```
Market Data → TA → SMC → MTF → Strategy (6) → ML (9) → Combined Signal (10)
  → PAXGUSD Instrument → Risk → Position Size → Margin → Costs → Trade Plan (11)
```

## Phase 11

| Layer | Location |
|-------|----------|
| Instruments | `backend/app/instruments/` |
| Risk / sizing / costs / margin | `backend/app/risk/` |
| API | `/api/risk/*` |
| Backtest modes | `risk_mode=FIXED_1R\|RISK_PERCENT` |
| UI | `RiskPanel` / Risk Management page |

**Non-goals:** live orders, API keys, automated trading, production deployment.
