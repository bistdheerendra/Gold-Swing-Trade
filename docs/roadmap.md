# Roadmap — Gold Swing AI

Master phased delivery (13 phases). **Do not skip ahead** without explicit approval.

| Phase | Name | Status |
|-------|------|--------|
| 0–10 | Foundation → Combined Signal | **COMPLETE** |
| 11 | Risk Management + Position Sizing | **COMPLETE** |
| 11.5 | Real Market Data Migration | **COMPLETE** |
| 11.6 | Strategy Recalibration on Real Data | **COMPLETE — NO-GO for Phase 12** |
| 11.7 | Diagnosis Review + Conditional Rule Revision | **COMPLETE — no rewrite; NO-GO** |
| 11.8 | Candle-Level ML Labeling | **COMPLETE — research; weak skill** |
| 12 | Paper Trading + Live Monitoring + Alerts | **BLOCKED** (await GO after more evidence) |
| 13 | Production Hardening & Deployment | Pending |

### Phase 11 — COMPLETE

PAXGUSD InstrumentSpec, RiskEngine, position sizing, margin/cost engines, daily/streak guards, FIXED_1R vs RISK_PERCENT backtest, Risk API + UI.  
**No** live orders. **No** API keys. **No** profitability claims.

### Phase 11.5 — COMPLETE

Replaced mock/synthetic default with free-tier **Delta Exchange India** (authoritative `PAXGUSD`, verified via `/v2/products`) + optional **Twelve Data** (`XAU/USD` reference). Added **30m** timeframe end-to-end (MTF hierarchy 1D→4H→1H→30M→15M). Mock gated behind `ALLOW_MOCK_DATA=true` (pytest only).

### Phase 11.7 — COMPLETE (no rewrite; NO-GO)

Reviewed Phase 11.6 evidence in plain language. Binding constraint is **sample thinness** (ALL n≈34, TEST n=6; Delta history already maxed ~Feb 2026 start), not a cleanly localized structural defect. **No Phase 6 rule changes.** See `docs/phase-11.7-diagnosis-review.md`.

### Phase 11.8 — COMPLETE (research; weak skill)

Candle-level ATR triple-barrier labels on full Delta history (~16k rows). Retrained Phase 9 baselines; ~2.7pp accuracy over majority on TEST — **not wired** to Phase 6/10. See `docs/ml-labeling.md`, `docs/phase-11.8-candle-ml-results.md`.

### Phase 12 — Paper Trading + Live Monitoring + Alerts

Simulated execution, monitoring, alerts. No production money until Phase 13 gates. **Requires a documented GO after sufficient real-data evidence.**

## Process rules

1. Build **one phase at a time**.
2. Start only when instructed: `START PHASE N`.
3. Do not rewrite completed engines unless fixing a proven bug.
4. WAIT / NO_TRADE remain first-class.
5. No look-ahead bias.

## Next

**Not** Phase 12. Candle ML is research-only; strategy expectancy gate still fails.
