# Phase 11.6 — Recalibration Results & Go/No-Go

**Generated:** 2026-08-09 (corrected gate after script review)  
**Decision:** `NO_GO` — do **not** start Phase 12

## Comparison table

| Run | Trades | Win rate | Expectancy (R) | Max DD % | Notes |
|-----|--------|----------|----------------|----------|-------|
| Original Phase 11.5 ref | 12 | 33.3% | **−0.19** | 5.8 | Small window; TEST warmup artifact → 0 Phase 10 trades |
| Expanded pre-recal **ALL** | 34 | 38.2% | **+0.072** | 5.4 | Max Delta history (~16k 15m bars from ~2026-02-19) |
| Expanded pre-recal **TEST** | 6 | 33.3% | **−0.39** | 3.9 | After measurement fix (full-series warmup) |
| Expanded post-recal **ALL** | 40 | 37.5% | **+0.010** | 5.4 | Vol penalty 8→5; **worse** than pre-recal ALL |
| Expanded post-recal **VAL** | 21 | 38.1% | +1.30 | 7.4 | Strong but not a gate by itself (tuning-adjacent slice) |
| Expanded post-recal **TEST** | 6 | 33.3% | **−0.39** | 3.9 | Unchanged vs pre-recal TEST |

Raw JSON from the calibration run:

```json
{
  "original_11_5_ref": {
    "trades_entered": 12,
    "win_rate": 0.333333,
    "expectancy_r": -0.193054,
    "max_drawdown_pct": 5.7784,
    "phase10_test_trades": 0
  },
  "expanded_pre_recal_all": {
    "trades_entered": 34,
    "win_rate": 0.382353,
    "expectancy_r": 0.071521,
    "max_drawdown_pct": 5.359
  },
  "expanded_pre_recal_test": {
    "trades_entered": 6,
    "win_rate": 0.333333,
    "expectancy_r": -0.390061,
    "max_drawdown_pct": 3.9282
  },
  "expanded_post_recal_all": {
    "trades_entered": 40,
    "win_rate": 0.375,
    "expectancy_r": 0.009657,
    "max_drawdown_pct": 5.4022
  },
  "expanded_post_recal_validation": {
    "trades_entered": 21,
    "win_rate": 0.380952,
    "expectancy_r": 1.302346,
    "max_drawdown_pct": 7.3504
  },
  "expanded_post_recal_test": {
    "trades_entered": 6,
    "win_rate": 0.333333,
    "expectancy_r": -0.390061,
    "max_drawdown_pct": 3.9282
  }
}
```

## Applied threshold changes (TRAIN/VAL evidence only)

| Field | Before | After | Adopted as default? | Rationale |
|-------|--------|-------|---------------------|-----------|
| `high_volatility_penalty` | 8.0 | 5.0 | **No** | Real 15m ATR% p50≈0.16; a few vol blocks on TRAIN+VAL. Candidate saved in `backend/app/strategy/config_real_recal.json` for audit only. |

`signal_threshold` (65) and `wait_threshold` (50) were **not** lowered — score p90 on TRAIN+VAL was 76 (≥65), so the gate was reachable; forcing trades would violate WAIT-first discipline.

## Phase 10 held-out TEST

- **RULE_ONLY after measurement fix:** 6 trades, expectancy **−0.39R** (not zero).
- Prior Phase 11.5 “0 trades” was largely a **warmup-after-slice bug** (TEST length &lt; warmup → zero evaluations). Fixed via `chronological_eval_bounds` + full-series context in `BacktestEngine`.
- **ML_FILTER:** not re-claimed here — no stable real-data ML edge asserted; RULE_ONLY already fails the gate.
- Non-trivial activity exists, but **WAIT/NO_TRADE remain appropriate**; sparse trading is not treated as a bug to “fix” by lowering thresholds.

## Go / No-Go decision

**NO-GO for Phase 12.**

Reasons (plain):

1. Held-out **TEST expectancy is negative** (−0.39R) on n=6 — statistically thin and losing.
2. Expanded **ALL** is only weakly positive (+0.07R pre-recal; +0.01R post-recal on n≈34–40). That is not a robust edge.
3. The only proposed recalibration **worsened ALL expectancy** and did **not** improve TEST — it is **not** adopted as the live default.
4. Paper-trading this rule set would mostly burn calendar confirming what the held-out slice already shows.

### Next steps (instead of Phase 12)

1. **Structural Phase 6 review** — confluence / location / RR gates, not more threshold grinding on this sample.
2. **Accumulate history** — Delta PAXGUSD listing only goes back to ~2026-02-19; n grows with time.
3. Keep the **measurement fix** (full-series warmup / eval bounds) and default `StrategyConfig` 1.0.0 thresholds.
4. Re-run Phase 11.6 gate when history or rule logic changes; only then consider `START PHASE 12`.

**Decision:** `NO_GO`
