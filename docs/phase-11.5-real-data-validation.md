# Phase 11.5 — Real Market Data Validation Report

**Generated:** 2026-08-09T05:04:37.763537+00:00
**Provider:** `binance`
**Symbol:** `PAXGUSD`

> Honest research report. Real-data metrics replace synthetic ones. Worse live metrics are expected and not hidden.

## Backfill

```json
{
  "15m": 2500,
  "1h": 1200,
  "4h": 600,
  "1d": 400
}
```

## Discarded synthetic artifacts

```json
[]
```

## Synthetic baseline (reference only)

```json
{
  "note": "Prior Phase 7\u20139 numbers were measured on mock/synthetic OHLCV (and/or small fixture windows). They are NOT a fair benchmark for live expectancy \u2014 listed only to show the migration delta.",
  "phase7_mock_reference": {
    "source": "synthetic mock provider / early research runs",
    "win_rate": "n/a (not frozen as production truth)",
    "expectancy_r": "n/a",
    "max_drawdown_pct": "n/a",
    "comment": "Synthetic series overfit-friendly; real-data results replace them."
  }
}
```

## Phase 7 — Rule backtest (real data)

```json
{
  "backtest_id": "f040c30c-ff26-4c7a-ad55-8dc014868b7f",
  "bars_used": {
    "15m": 1500,
    "1h": 1200,
    "4h": 600,
    "1d": 400
  },
  "metrics": {
    "trades_entered": 17,
    "win_rate": 0.529412,
    "expectancy_r": 0.782274,
    "profit_factor": 2.386577,
    "max_drawdown_pct": 3.1842,
    "net_profit_r": 13.298662,
    "average_r": 0.782274,
    "final_equity": 33989.5986
  },
  "notes": [
    "RULE_ONLY on real Binance-proxied PAXGUSD candles",
    "Costs/slippage included (REALISTIC_COST)",
    "Results expected to differ from synthetic \u2014 reported honestly"
  ]
}
```

## Phase 8 — ML dataset (real data)

```json
{
  "dataset_id": "d3d41af5-0a5f-4186-b140-4b8839e3c346",
  "rows": 540,
  "train": 378,
  "validation": 81,
  "test": 81,
  "feature_version": "1.0.0",
  "label_version": "1.0.0",
  "chronological_splits": true,
  "source": "real_binance"
}
```

## Phase 9 — ML training (real data)

```json
{
  "model_id": "direction_gradient_boosting_bfcb716a",
  "selected_model_type": "gradient_boosting",
  "train_metrics": {
    "accuracy": 1.0,
    "balanced_accuracy": 1.0,
    "precision_macro": 1.0,
    "recall_macro": 1.0,
    "f1_macro": 1.0,
    "confusion_matrix": {
      "DOWN": {
        "DOWN": 83,
        "NEUTRAL": 0,
        "UP": 0
      },
      "NEUTRAL": {
        "DOWN": 0,
        "NEUTRAL": 196,
        "UP": 0
      },
      "UP": {
        "DOWN": 0,
        "NEUTRAL": 0,
        "UP": 99
      }
    },
    "support": {
      "UP": 99,
      "DOWN": 83,
      "NEUTRAL": 196
    },
    "n": 378
  },
  "validation_metrics": {
    "accuracy": 0.271605,
    "balanced_accuracy": 0.304356,
    "precision_macro": 0.274643,
    "recall_macro": 0.304356,
    "f1_macro": 0.27712,
    "confusion_matrix": {
      "DOWN": {
        "DOWN": 10,
        "NEUTRAL": 5,
        "UP": 4
      },
      "NEUTRAL": {
        "DOWN": 10,
        "NEUTRAL": 5,
        "UP": 11
      },
      "UP": {
        "DOWN": 10,
        "NEUTRAL": 19,
        "UP": 7
      }
    },
    "support": {
      "UP": 36,
      "NEUTRAL": 26,
      "DOWN": 19
    },
    "n": 81
  },
  "test_metrics": {
    "accuracy": 0.567901,
    "balanced_accuracy": 0.454203,
    "precision_macro": 0.477017,
    "recall_macro": 0.454203,
    "f1_macro": 0.444404,
    "confusion_matrix": {
      "DOWN": {
        "DOWN": 3,
        "NEUTRAL": 3,
        "UP": 4
      },
      "NEUTRAL": {
        "DOWN": 8,
        "NEUTRAL": 36,
        "UP": 2
      },
      "UP": {
        "DOWN": 8,
        "NEUTRAL": 10,
        "UP": 7
      }
    },
    "support": {
      "NEUTRAL": 46,
      "UP": 25,
      "DOWN": 10
    },
    "n": 81
  },
  "scores": {
    "train": 1.0,
    "validation": 0.27712,
    "test": 0.444404
  },
  "notes": [
    "RESEARCH ONLY \u2014 not production",
    "Model selection used VALIDATION only",
    "TEST evaluated once after selection",
    "Thresholds scanned on VALIDATION only",
    "No GridSearch / Optuna / deep learning"
  ]
}
```

## Phase 10 — RULE_ONLY vs ML_FILTER

```json
{
  "threshold": 0.5,
  "rule_only_test": {
    "trades_entered": 2,
    "win_rate": 1.0,
    "expectancy_r": 4.149637,
    "profit_factor": 999.0,
    "max_drawdown_pct": 0.0,
    "net_profit_r": 8.299274,
    "average_r": 4.149637,
    "final_equity": 108299.274
  },
  "ml_filter_test": {
    "trades_entered": 2,
    "win_rate": 1.0,
    "expectancy_r": 4.149637,
    "profit_factor": 999.0,
    "max_drawdown_pct": 0.0,
    "net_profit_r": 8.299274,
    "average_r": 4.149637,
    "final_equity": 108299.274
  },
  "comparison_note": "Do not assume ML improves expectancy. Both sides reported."
}
```

## Phase 11 — Risk engine sanity

```json
{
  "ok": true,
  "symbol": "PAXGUSD",
  "last_price": 4344.62,
  "atr_14_1h": 4.593359805199083,
  "atr_pct": 0.10572523730957098,
  "price_source": "real_binance",
  "trade_plan": {
    "risk_status": "POSITION_LIMIT_EXCEEDED",
    "quantity": 524.0,
    "risk_amount": 300.0,
    "risk_amount_usd": 3.6144578313253013,
    "entry": 4344.62,
    "stop_loss": 4337.73,
    "notional_value": 2276.5809,
    "reasons": [
      "INSUFFICIENT_MARGIN / MARGIN_LIMIT: need 37791.24 INR but usable after 20.0% buffer is 24000.00. Reduce quantity (do not raise leverage).",
      "POSITION_LIMIT_EXCEEDED: required margin 37791.24 > 30.0% of balance (9000.00). Reduce quantity (do not raise leverage)."
    ],
    "risks": []
  },
  "notes": [
    "ATR and price levels from real candles (not synthetic ~2300 mock)",
    "Position size must track real stop distance / volatility"
  ]
}
```

## Verdict

Phase 11.5 validation completed on real Binance PAXGUSDT-proxied PAXGUSD data. Synthetic-trained model artifacts were discarded. Ready for Phase 12 only if backfill + Phase 7–11 sections above are green and PROJECT.md checklist is updated.
