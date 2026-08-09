# Phase 11.8 — Candle-Level ML Results

**Generated:** 2026-08-09T11:28:16.219828+00:00

## Constants (a priori)

- `N` (horizon bars) = **8**
- `k` (ATR multiple) = **1.0**
- ATR period = **14**

See [docs/ml-labeling.md](ml-labeling.md). Not retuned after TEST.

## Dataset

- dataset_id: `21f43639-8866-4dbe-a7e8-301f2c9bc809`
- rows: **16294** (source 15m bars: 16382)
- range: `2026-02-20T09:45:00+00:00` → `2026-08-09T03:00:00+00:00`
- output: `C:\Users\admin\Desktop\Gold Trader\data\ml_datasets_candle\21f43639-8866-4dbe-a7e8-301f2c9bc809`
- Phase 8 path untouched: `data/ml_datasets/`

### Split date ranges

```json
{
  "train": {
    "start": "2026-02-20T09:45:00+00:00",
    "end": "2026-06-19T04:45:00+00:00",
    "n": 11405
  },
  "validation": {
    "start": "2026-06-19T05:00:00+00:00",
    "end": "2026-07-14T15:45:00+00:00",
    "n": 2444
  },
  "test": {
    "start": "2026-07-14T16:00:00+00:00",
    "end": "2026-08-09T03:00:00+00:00",
    "n": 2445
  }
}
```

### Class distribution (UP / DOWN / FLAT)

```json
{
  "all": {
    "counts": {
      "UP": 6903,
      "DOWN": 7420,
      "FLAT": 1971
    },
    "pct": {
      "DOWN": 0.4554,
      "FLAT": 0.121,
      "UP": 0.4237
    },
    "n": 16294
  },
  "train": {
    "counts": {
      "UP": 4845,
      "DOWN": 5230,
      "FLAT": 1330
    },
    "pct": {
      "DOWN": 0.4586,
      "FLAT": 0.1166,
      "UP": 0.4248
    },
    "n": 11405
  },
  "validation": {
    "counts": {
      "UP": 979,
      "DOWN": 1186,
      "FLAT": 279
    },
    "pct": {
      "DOWN": 0.4853,
      "FLAT": 0.1142,
      "UP": 0.4006
    },
    "n": 2444
  },
  "test": {
    "counts": {
      "FLAT": 362,
      "DOWN": 1004,
      "UP": 1079
    },
    "pct": {
      "DOWN": 0.4106,
      "FLAT": 0.1481,
      "UP": 0.4413
    },
    "n": 2445
  }
}
```

## Model evaluation (held-out TEST once)

- Selected model: `gradient_boosting`

### Validation metrics

```json
{
  "accuracy": 0.46072,
  "balanced_accuracy": 0.356784,
  "precision_macro": 0.403249,
  "recall_macro": 0.356784,
  "f1_macro": 0.353482,
  "confusion_matrix": {
    "DOWN": {
      "DOWN": 692,
      "FLAT": 26,
      "UP": 468
    },
    "FLAT": {
      "DOWN": 153,
      "FLAT": 17,
      "UP": 109
    },
    "UP": {
      "DOWN": 547,
      "FLAT": 15,
      "UP": 417
    }
  },
  "support": {
    "UP": 979,
    "DOWN": 1186,
    "FLAT": 279
  },
  "n": 2444
}
```

### Test metrics

```json
{
  "accuracy": 0.438037,
  "balanced_accuracy": 0.364023,
  "precision_macro": 0.451286,
  "recall_macro": 0.364023,
  "f1_macro": 0.35649,
  "confusion_matrix": {
    "DOWN": {
      "DOWN": 615,
      "FLAT": 14,
      "UP": 375
    },
    "FLAT": {
      "DOWN": 178,
      "FLAT": 31,
      "UP": 153
    },
    "UP": {
      "DOWN": 634,
      "FLAT": 20,
      "UP": 425
    }
  },
  "support": {
    "FLAT": 362,
    "DOWN": 1004,
    "UP": 1079
  },
  "n": 2445
}
```

### Majority-class baseline (TEST)

```json
{
  "accuracy": 0.410634,
  "balanced_accuracy": 0.333333,
  "precision_macro": 0.136878,
  "recall_macro": 0.333333,
  "f1_macro": 0.194066,
  "confusion_matrix": {
    "DOWN": {
      "DOWN": 1004,
      "FLAT": 0,
      "UP": 0
    },
    "FLAT": {
      "DOWN": 362,
      "FLAT": 0,
      "UP": 0
    },
    "UP": {
      "DOWN": 1079,
      "FLAT": 0,
      "UP": 0
    }
  },
  "support": {
    "FLAT": 362,
    "DOWN": 1004,
    "UP": 1079
  },
  "n": 2445
}
```

**Skill vs majority (accuracy Δ):** `0.0274`

## Honesty notes

- **FLAT did not dominate** under the a priori `N=8`, `k=1.0` rule (FLAT ≈ 12% overall). Barriers of 1×ATR are hit often within 2 hours on this PAXGUSD window — reported as measured, not rebalanced.
- Test **accuracy 43.8%** vs majority **41.1%** is a thin lift (~2.7pp). **Balanced accuracy ~0.36** vs majority ~0.33. Not strong evidence of robust directional skill.
- Confusion matrices show heavy UP↔DOWN confusion; FLAT recall is poor.
- Logistic regression hit an sklearn convergence warning; selected model was **gradient_boosting** on validation.

## Verdict

**WEAK_SIGNAL — research only; do not wire to Phase 6/10; Phase 12 remains NO-GO**

Model beats majority baseline by Δacc≈0.027 on held-out TEST. That is not enough to claim a trading edge or clear paper-trading gates. Candle-level labeling solved the **thin-sample** problem (16 294 rows vs ~34 trade labels); it did **not** by itself produce a production-ready directional model.

## Constraints honored

- Full history used (not UI `bar_limit=220`)
- Features causal; labels forward-looking by design
- Chronological 70/15/15 split
- Phase 6 / Phase 10 pipelines untouched
- Phase 12 remains blocked pending strategy GO
