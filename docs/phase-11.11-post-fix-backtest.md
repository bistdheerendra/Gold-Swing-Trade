# Phase 11.11 — Post-Fix Backtest Re-Run (SL Geometry)

**Generated:** 2026-08-12T09:59:38.002384+00:00
**Symbol:** PAXGUSD (Delta India CSV, same window as Phase 11.6)
**Only variable:** `signal_engine._stop_loss` (Path B entry-anchored SL)
**Unchanged:** thresholds, sweep lookback, 1H→15m sweep source rule, splits, costs

> Controlled before/after. Does not expand history or retune strategy.

## 0. Window & methodology

```json
{
  "15m_bars": 16382,
  "matches_phase_11_6": true,
  "eval_index_test": [
    13924,
    16382
  ],
  "eval_index_train_val": [
    0,
    13924
  ]
}
```

- Entry TF: 15m · RULE_ONLY · REALISTIC_COST · FIXED_1R research normalization
- Steps: ALL / TRAIN+VAL `step=24`; TEST `step=12` (identical to Phase 11.6 baseline)
- Warmup 80 · max_context_bars 400 · AmbiguityPolicy.CONSERVATIVE
- Pre-fix baseline: monkeypatched Phase 11.6 price-anchored `_stop_loss` on the same codepath
- Legacy ALL/TEST re-runs reproduced Phase 11.6 published metrics exactly (n=34 / n=6)

## 1. Before / after comparison

### TRAIN+VAL

| Metric | Phase 11.6 (pre-fix)* | Phase 11.11 (post-fix) |
|--------|----------------------|--------------------------|
| Trade count | 31 | 49 |
| Win rate | 41.9% | 38.8% |
| Expectancy (R) | +0.191 | +0.161 |
| Profit factor | 1.288 | 1.244 |
| Max drawdown % | 5.36 | 11.41 |

\* Phase 11.6 did not publish combined TRAIN+VAL pre-recal metrics; pre-fix column is the controlled legacy `_stop_loss` re-run on the same CSV.

### TEST (held-out)

| Metric | Phase 11.6 (pre-fix) | Phase 11.11 (post-fix) |
|--------|----------------------|--------------------------|
| Trade count | 6 | 9 |
| Win rate | 33.3% | 44.4% |
| Expectancy (R) | -0.390 | +0.408 |
| Profit factor | 0.552 | 1.620 |
| Max drawdown % | 3.93 | 5.40 |

Legacy TEST re-run matched published Phase 11.6 (n=6, E[R]=-0.3901).

### ALL (reference, same as Phase 11.6 headline)

| Metric | Phase 11.6 (pre-fix) | Phase 11.11 (post-fix) |
|--------|----------------------|--------------------------|
| Trade count | 34 | 53 |
| Win rate | 38.2% | 35.8% |
| Expectancy (R) | +0.072 | +0.070 |
| Profit factor | 1.101 | 1.102 |
| Max drawdown % | 5.36 | 11.41 |

Legacy ALL re-run matched published Phase 11.6 (n=34, E[R]=0.0715).

## 2. Invalid-SL unblocks (signal-level, authoritative)

At each Phase 11.6 evaluation index, compare legacy vs fixed `StrategyEngine.analyze` without simulator path dependence. Count cases where legacy fails SL geometry validation (`"BUY/SELL SL must be … entry"` / wrong-side levels + validation block) and fixed emits BUY or SELL.

### TRAIN+VAL

```json
{
  "samples": 577,
  "step": 24,
  "legacy_sl_geometry_blocks": 214,
  "unblocked_to_buy_sell": 172,
  "still_blocked_after_fix": 0
}
```

**172** evaluation points convert legacy SL-geometry NO_TRADE → BUY/SELL after the fix. Of those, **32** also become entered trades in the post-fix ALL backtest (rest blocked by simulator path / non-overlap with entry fills). Full unblock list: JSON `signal_audit_train_val.unblocks`.

| # | Time | Fixed dir | Score | SL | Backtest net R | Outcome |
|---|------|-----------|-------|----|----------------|---------|
| 1 | 2026-02-25T09:45:00+00:00 | BUY | 70 | 5170.3255 | +3.507 | win |
| 2 | 2026-03-02T09:45:00+00:00 | BUY | 70 | 5397.231 | -1.017 | loss |
| 3 | 2026-03-04T21:45:00+00:00 | SELL | 65 | 5178.6333 | -1.070 | loss |
| 4 | 2026-03-08T15:45:00+00:00 | BUY | 70 | 5156.2554 | -1.022 | loss |
| 5 | 2026-03-13T21:45:00+00:00 | SELL | 70 | 5039.2889 | -1.018 | loss |
| 6 | 2026-03-18T21:45:00+00:00 | SELL | 70 | 4831.2506 | +2.708 | win |
| 7 | 2026-03-22T15:45:00+00:00 | SELL | 70 | 4498.3474 | -1.038 | loss |
| 8 | 2026-03-24T03:45:00+00:00 | SELL | 77 | 4431.7288 | +0.640 | win |
| 9 | 2026-03-26T21:45:00+00:00 | SELL | 70 | 4439.3818 | -1.008 | loss |
| 10 | 2026-03-27T03:45:00+00:00 | SELL | 85 | 4513.3868 | +1.393 | win |
| 11 | 2026-03-29T09:45:00+00:00 | SELL | 70 | 4499.0745 | -1.189 | loss |
| 12 | 2026-04-01T03:45:00+00:00 | BUY | 65 | 4658.813 | -1.073 | loss |
| 13 | 2026-04-02T03:45:00+00:00 | BUY | 66 | 4616.4068 | -1.027 | loss |
| 14 | 2026-04-16T09:45:00+00:00 | BUY | 75 | 4789.1916 | +1.619 | win |
| 15 | 2026-04-16T15:45:00+00:00 | BUY | 66 | 4757.5591 | -1.019 | loss |
| 16 | 2026-04-21T03:45:00+00:00 | BUY | 85 | 4755.6488 | -1.015 | loss |
| 17 | 2026-04-26T09:45:00+00:00 | SELL | 65 | 4695.9523 | -1.139 | loss |
| 18 | 2026-04-26T21:45:00+00:00 | BUY | 75 | 4691.3723 | -1.074 | loss |
| 19 | 2026-05-04T21:45:00+00:00 | SELL | 70 | 4548.3751 | -1.009 | loss |
| 20 | 2026-05-07T15:45:00+00:00 | BUY | 65 | 4690.0748 | -1.010 | loss |
| 21 | 2026-05-12T03:45:00+00:00 | BUY | 90 | 4693.0959 | -1.032 | loss |
| 22 | 2026-05-21T15:45:00+00:00 | SELL | 100 | 4529.3039 | -1.031 | loss |
| 23 | 2026-05-24T15:45:00+00:00 | BUY | 67 | 4514.8534 | +1.219 | win |
| 24 | 2026-05-27T03:45:00+00:00 | SELL | 70 | 4518.1741 | -1.121 | loss |
| 25 | 2026-05-28T09:45:00+00:00 | SELL | 70 | 4412.8682 | +2.049 | win |
| 26 | 2026-05-31T21:45:00+00:00 | SELL | 95 | 4537.5379 | +8.442 | win |
| 27 | 2026-06-01T09:45:00+00:00 | SELL | 85 | 4503.9417 | -1.117 | loss |
| 28 | 2026-06-02T03:45:00+00:00 | SELL | 90 | 4526.6101 | -1.094 | loss |
| 29 | 2026-06-06T21:45:00+00:00 | SELL | 70 | 4292.0261 | +0.938 | win |
| 30 | 2026-06-22T09:45:00+00:00 | BUY | 67 | 4176.0275 | +1.768 | win |
| 31 | 2026-07-08T09:45:00+00:00 | SELL | 70 | 4109.1441 | +0.677 | win |
| 32 | 2026-07-14T03:45:00+00:00 | SELL | 67 | 4037.1542 | -1.013 | loss |

Entered unblocks: **11W / 21L**, sum R = **+2.825**, mean R = **+0.088**.

### TEST

```json
{
  "samples": 205,
  "step": 12,
  "legacy_sl_geometry_blocks": 64,
  "unblocked_to_buy_sell": 59,
  "still_blocked_after_fix": 0
}
```

**59** TEST points unblock to BUY/SELL; **5** entered in the post-fix TEST backtest. Full list: JSON `signal_audit_test.unblocks`.

| # | Time | Fixed dir | Score | SL | Backtest net R | Outcome |
|---|------|-----------|-------|----|----------------|---------|
| 1 | 2026-07-16T14:45:00+00:00 | SELL | 70 | 4016.7761 | +5.483 | win |
| 2 | 2026-07-29T14:45:00+00:00 | SELL | 85 | 4037.3661 | -1.066 | loss |
| 3 | 2026-07-29T17:45:00+00:00 | SELL | 90 | 4050.9583 | -1.030 | loss |
| 4 | 2026-07-30T02:45:00+00:00 | BUY | 65 | 4028.1828 | -1.025 | loss |
| 5 | 2026-08-07T11:45:00+00:00 | BUY | 70 | 4287.0472 | -1.054 | loss |

Entered TEST unblocks: sum R = **+1.308**, mean R = **+0.262** (1W / 4L).

#### TEST membership newly-included trades (path-dependent)

| # | Time | Dir | Score | Net R | Outcome | Exit |
|---|------|-----|-------|-------|---------|------|
| 1 | 2026-07-16T14:45:00+00:00 | SELL | 70 | +5.483 | win | TP1 |
| 2 | 2026-07-29T14:45:00+00:00 | SELL | 85 | -1.066 | loss | SL |
| 3 | 2026-07-29T17:45:00+00:00 | SELL | 90 | -1.030 | loss | SL |
| 4 | 2026-07-30T02:45:00+00:00 | BUY | 65 | -1.025 | loss | SL |
| 5 | 2026-08-07T11:45:00+00:00 | BUY | 70 | -1.054 | loss | SL |

## 3. Entered-trade membership diffs (includes path dependence)

Simulator concurrency means adding an early trade can displace a later one. Treat these as secondary to §2.

### TRAIN+VAL

- Membership: legacy n=31 → fixed n=49 (+32 / −14); SL/R changed on overlap=6

### TEST

- Membership: legacy n=6 → fixed n=9 (+5 / −2); SL/R changed on overlap=1

### ALL

- Membership: legacy n=34 → fixed n=53 (+34 / −15); SL/R changed on overlap=7

## 4. Why the change happened

- Signal-level SL-geometry blocks on TRAIN+VAL: **214** (of 577 stepped samples)
- Of those, **172** become BUY/SELL after the fix; **32** enter the ALL simulator
- TEST: **64** blocks → **59** BUY/SELL → **5** entered
- Entered TRAIN+VAL/ALL unblocks are mixed (more losses than wins on the filled subset) — the bug was **not** systematically filtering only bad trades, nor only good ones
- ALL expectancy barely moves because added trades dilute win rate and increase drawdown even when mean R of the filled-unblock subset is near zero

## 5. Phase 12 gate restatement

**Decision: `NO_GO`**

- TEST n=9 still far too thin to trust (was n=6; now n=9)
- TEST expectancy flipped to +0.408R — interesting but not defendable on this sample
- ALL expectancy essentially unchanged (+0.070R on n=53 vs +0.072R on n=34) while max DD roughly doubled (~5.4% → ~11.4%)
- TRAIN+VAL expectancy slightly worse (+0.161R on n=49 vs +0.191R on n=31)
- single controlled SL fix is one data point, not full re-validation

- Post-fix TEST: **+0.408** on n=9 (was −0.390R on n=6)
- Post-fix TRAIN+VAL: **+0.161** on n=49
- Post-fix ALL: **+0.070** on n=53 (was +0.072R on n=34)

Phase 12 still **NO-GO**. The SL geometry fix is correct and should stay; it does not create a trustworthy edge on this history depth.

## 6. Raw run metrics

```json
{
  "legacy:ALL": {
    "trades_entered": 34,
    "total_signals": 44,
    "signals_expired": 10,
    "win_rate": 0.382353,
    "expectancy_r": 0.071521,
    "profit_factor": 1.101198,
    "max_drawdown_pct": 5.359,
    "net_profit_r": 2.431716,
    "average_r": 0.071521,
    "final_equity": 30729.5148,
    "notes": [
      "split=ALL",
      "eval_bars=16382",
      "context_bars=16382",
      "eval_index=[0,16382)",
      "signal_mode=RULE_ONLY",
      "risk_mode=FIXED_1R: FIXED_1R uses initial_equity * risk_fraction (research normalization).",
      "ambiguity_policy=CONSERVATIVE",
      "cost_mode=REALISTIC_COST"
    ]
  },
  "fixed:ALL": {
    "trades_entered": 53,
    "total_signals": 218,
    "signals_expired": 165,
    "win_rate": 0.358491,
    "expectancy_r": 0.069786,
    "profit_factor": 1.101565,
    "max_drawdown_pct": 11.4145,
    "net_profit_r": 3.698683,
    "average_r": 0.069786,
    "final_equity": 31109.6049,
    "notes": [
      "split=ALL",
      "eval_bars=16382",
      "context_bars=16382",
      "eval_index=[0,16382)",
      "signal_mode=RULE_ONLY",
      "risk_mode=FIXED_1R: FIXED_1R uses initial_equity * risk_fraction (research normalization).",
      "ambiguity_policy=CONSERVATIVE",
      "cost_mode=REALISTIC_COST"
    ]
  },
  "legacy:TRAIN_VAL": {
    "trades_entered": 31,
    "total_signals": 39,
    "signals_expired": 8,
    "win_rate": 0.419355,
    "expectancy_r": 0.190858,
    "profit_factor": 1.287989,
    "max_drawdown_pct": 5.359,
    "net_profit_r": 5.916596,
    "average_r": 0.190858,
    "final_equity": 31774.9788,
    "notes": [
      "split=TRAIN+VAL",
      "eval_bars=13924",
      "context_bars=16382",
      "eval_index=[0,13924)",
      "signal_mode=RULE_ONLY",
      "risk_mode=FIXED_1R: FIXED_1R uses initial_equity * risk_fraction (research normalization).",
      "ambiguity_policy=CONSERVATIVE",
      "cost_mode=REALISTIC_COST"
    ]
  },
  "fixed:TRAIN_VAL": {
    "trades_entered": 49,
    "total_signals": 193,
    "signals_expired": 144,
    "win_rate": 0.387755,
    "expectancy_r": 0.160747,
    "profit_factor": 1.244321,
    "max_drawdown_pct": 11.4145,
    "net_profit_r": 7.876627,
    "average_r": 0.160747,
    "final_equity": 32362.9881,
    "notes": [
      "split=TRAIN+VAL",
      "eval_bars=13924",
      "context_bars=16382",
      "eval_index=[0,13924)",
      "signal_mode=RULE_ONLY",
      "risk_mode=FIXED_1R: FIXED_1R uses initial_equity * risk_fraction (research normalization).",
      "ambiguity_policy=CONSERVATIVE",
      "cost_mode=REALISTIC_COST"
    ]
  },
  "legacy:TEST": {
    "trades_entered": 6,
    "total_signals": 6,
    "signals_expired": 0,
    "win_rate": 0.333333,
    "expectancy_r": -0.390061,
    "profit_factor": 0.551935,
    "max_drawdown_pct": 3.9282,
    "net_profit_r": -2.340367,
    "average_r": -0.390061,
    "final_equity": 29297.8899,
    "notes": [
      "split=TEST",
      "eval_bars=2458",
      "context_bars=16382",
      "eval_index=[13924,16382)",
      "signal_mode=RULE_ONLY",
      "risk_mode=FIXED_1R: FIXED_1R uses initial_equity * risk_fraction (research normalization).",
      "ambiguity_policy=CONSERVATIVE",
      "cost_mode=REALISTIC_COST"
    ]
  },
  "fixed:TEST": {
    "trades_entered": 9,
    "total_signals": 42,
    "signals_expired": 33,
    "win_rate": 0.444444,
    "expectancy_r": 0.407733,
    "profit_factor": 1.620064,
    "max_drawdown_pct": 5.4003,
    "net_profit_r": 3.669596,
    "average_r": 0.407733,
    "final_equity": 31100.8788,
    "notes": [
      "split=TEST",
      "eval_bars=2458",
      "context_bars=16382",
      "eval_index=[13924,16382)",
      "signal_mode=RULE_ONLY",
      "risk_mode=FIXED_1R: FIXED_1R uses initial_equity * risk_fraction (research normalization).",
      "ambiguity_policy=CONSERVATIVE",
      "cost_mode=REALISTIC_COST"
    ]
  }
}
```

Companion JSON: `docs/phase-11.11-post-fix-backtest.json`.
Repro script: `backend/scripts/phase_11_11_post_fix_backtest.py`.
