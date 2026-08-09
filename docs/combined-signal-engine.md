# Combined Signal Engine (Phase 10)

Rule engine detects setups. ML filters trade quality. Combined produces final research signal.

```
RULE ENGINE → SETUP (BUY/SELL/WAIT/NO_TRADE)
ML MODEL    → ACCEPT / REJECT / WAIT
COMBINED    → FINAL DECISION
```

## Hard rules

- If rule is `WAIT` or `NO_TRADE`, ML **cannot** invent BUY/SELL.
- ML confidence is **not** a guaranteed win probability (`probability_calibrated` flag).
- Thresholds freeze from **VALIDATION**; TEST is evaluated once.

## Decision matrix

| Rule | ML | Confidence | Final |
|------|-----|------------|-------|
| BUY | BUY | ≥ thr | BUY |
| SELL | SELL | ≥ thr | SELL |
| BUY | SELL | any | NO_TRADE |
| SELL | BUY | any | NO_TRADE |
| BUY/SELL | aligned | < thr | WAIT |
| WAIT | * | * | WAIT |
| NO_TRADE | * | * | NO_TRADE |

## Fallback

- `ML_UNAVAILABLE` → config `FALLBACK_RULE` or `WAIT`
- `MODEL_INCOMPATIBLE` → no prediction; same fallback

## Code

- `backend/app/combined/`
- API: `GET /api/combined/analyze`, `POST /api/combined/compare`, alias `GET /api/ml/signal`
