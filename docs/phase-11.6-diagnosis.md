# Phase 11.6 — Strategy Diagnosis (Real PAXGUSD / Delta India)

**Generated:** 2026-08-09T05:42:03.542017+00:00

> Diagnosis written **before** threshold changes. No test-slice peeking.

## 1. Expanded historical window

```json
{
  "15m": {
    "bars": 16382,
    "csv": "PAXGUSD_15m.csv",
    "reused": true
  },
  "30m": {
    "bars": 8192,
    "csv": "PAXGUSD_30m.csv",
    "reused": true
  },
  "1h": {
    "bars": 4097,
    "csv": "PAXGUSD_1h.csv",
    "reused": true
  },
  "4h": {
    "bars": 1025,
    "csv": "PAXGUSD_4h.csv",
    "reused": true
  },
  "1d": {
    "bars": 172,
    "csv": "PAXGUSD_1d.csv",
    "reused": true
  }
}
```

## 2. Baseline backtests (pre-recalibration)

### Original Phase 11.5 reference (small window / prior run)

```json
{
  "source": "Phase 11.5 validate_phase_11_5 Delta run (conversation)",
  "trades_entered": 12,
  "win_rate": 0.333333,
  "expectancy_r": -0.193054,
  "max_drawdown_pct": 5.7784,
  "phase10_test_trades": 0,
  "note": "Smaller capped window + TEST warmup-after-slice measurement artifact"
}
```

### Expanded window — ALL (pre-recal, default thresholds)

```json
{
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
}
```

### Expanded window — TEST (pre-recal, after measurement fix)

```json
{
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
}
```

## 3. Root cause — Phase 10 zero trades

```json
{
  "samples": 80,
  "diagnose_window": "TRAIN+VALIDATION only (TEST untouched)",
  "direction_counts": {
    "NO_TRADE": 42,
    "WAIT": 36,
    "SELL": 2
  },
  "score_bands": {
    "<50": 4,
    "50-64": 37,
    "65-79": 33,
    "80+": 6
  },
  "score_distribution": {
    "n": 80,
    "p10": 51.0,
    "p50": 62.0,
    "p90": 76.0,
    "mean": 64.025
  },
  "near_miss_wait_band_count": 37,
  "near_miss_rate": 0.4625,
  "blocked_high_score_reasons": {
    "\u26a0 Location: Dealing zone DISCOUNT": 13,
    "\u26a0 Entry timeframe confirmation incomplete": 8,
    "\u26a0 All layers oppose proposed direction": 6,
    "\u26a0 Elevated ATR (high volatility)": 3,
    "\u26a0 Location: Price near equilibrium": 3,
    "\u26a0 Location: Dealing zone PREMIUM": 3,
    "\u26a0 RR 1.08 below minimum 1.5": 3,
    "\u2717 OB/Demand/Supply: Price not near active zone": 3
  },
  "rsi_distribution": {
    "n": 80,
    "p10": 34.3916,
    "p50": 49.1298,
    "p90": 66.8028,
    "mean": 48.7963
  },
  "adx_distribution": {
    "n": 80,
    "p10": 16.0609,
    "p50": 23.2622,
    "p90": 40.6979,
    "mean": 25.4579
  },
  "atr_pct_distribution": {
    "n": 80,
    "p10": 0.0424,
    "p50": 0.1584,
    "p90": 0.2853,
    "mean": 0.1644
  },
  "synthetic_reference_notes": {
    "mock_base_price_era": "~2300 then ~4340",
    "mtf_rsi_bull_bear": ">=55 / <=45",
    "mtf_adx_filter": ">=20",
    "strategy_signal_threshold": 65,
    "strategy_wait_threshold": 50,
    "atr_pct_on_real_gold_~4340": "typically ~0.1% per 1h ATR vs larger relative moves on synthetic"
  },
  "phase10_zero_trade_hypothesis": {
    "measurement_bug": "Prior engine sliced TEST first then applied warmup_bars on the short slice \u2014 if TEST length < warmup, zero evaluations. Fixed in Phase 11.6 to keep full-series context and evaluate only inside segment bounds.",
    "strategy_conservatism": "Score>=65 requires multi-condition SMC confluence; WAIT/NO_TRADE dominance may be correct on ranging real gold."
  },
  "phase10_post_fix_note": "After the measurement fix, expanded TEST RULE_ONLY produced 6 trades (not 0). Zero-trade Phase 11.5 result was primarily a measurement artifact; remaining issue is negative TEST expectancy, not silence."
}
```

## 4. Proposed recalibration (TRAIN/VAL evidence only)

```json
[
  {
    "field": "high_volatility_penalty",
    "before": 8.0,
    "after": 5.0,
    "rationale": "Real 15m ATR% p50=0.1584 is small in absolute gold terms; 3 vol-related blocks observed. Penalty 8\u21925 (still active)."
  }
]
```
