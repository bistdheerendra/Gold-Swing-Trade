# API — Gold Swing AI

**Phase:** 11

## System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | `phase: "11"` |
| GET | `/api/health` | `phase: 11` |

## Risk (Phase 11 — RESEARCH)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/risk/analyze` | Phase 10 signal → TradePlan |
| POST | `/api/risk/backtest` | RISK_PERCENT / FIXED_1R simulation |
| GET | `/api/risk/config` | Account risk config |
| PUT | `/api/risk/config` | Update config (no secrets) |
| GET | `/api/risk/instruments` | Instrument registry |
| GET | `/api/risk/paxgusd/spec` | PAXGUSD adapter spec |
| GET | `/api/risk/ruin` | Research ruin estimate |

Analyze query params: `symbol`, `as_of`, `account_balance`, `risk_percent`, `leverage`, `minimum_rr`.

Backtest `POST /api/backtest/run` also accepts `risk_mode` (`FIXED_1R` | `RISK_PERCENT`).

## Combined signals (Phase 10)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/combined/analyze` | Rule + ML combined signal |
| POST | `/api/combined/compare` | RULE_ONLY vs ML_FILTER |

**Not present:** `/trade`, `/order`, `place_order`, broker API key storage.
