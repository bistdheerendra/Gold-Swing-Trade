# Binance PAXGUSDT Candle ML — Research Sidecar

**Generated:** 2026-08-12T11:43:29.902937+00:00

> Separate from Delta PAXGUSD. Suggestions only — not Phase 12 GO.

## Setup

```powershell
cd backend
.\.venv\Scripts\python.exe scripts/backfill_binance_paxgusdt.py
.\.venv\Scripts\python.exe scripts/phase_binance_paxgusdt_candle_ml.py
```

- API: `GET /api/research/binance-suggest`
- UI: Dashboard panel **Binance-trained · reference**
- Artifacts: `artifacts/ml_candle_binance/` (`SELECTED_MODEL_ID.txt`)
- CSVs: `data/historical/PAXGUSDT_*.csv` (never overwrites `PAXGUSD_*`)

## Auto weekly update

While the FastAPI process is running and `BINANCE_WEEKLY_UPDATE_ENABLED=true` (default), a background scheduler checks hourly and, every **7 days** since the last success, runs:

1. `scripts/backfill_binance_paxgusdt.py`
2. `scripts/phase_binance_paxgusdt_candle_ml.py`

State file: `artifacts/ml_candle_binance/LAST_WEEKLY_UPDATE.json`

| Action | How |
|--------|-----|
| Status | `GET /api/research/binance-weekly-status` |
| Queue now | `POST /api/research/binance-weekly-update?force=true` |
| CLI status | `python scripts/binance_weekly_update.py --status` |
| CLI force | `python scripts/binance_weekly_update.py --force` |

Disable with `BINANCE_WEEKLY_UPDATE_ENABLED=false`. If a selected model already exists, the weekly clock is seeded from that artifact’s mtime (no immediate retrain on first API start).

## Latest train result

- Symbol: `PAXGUSDT`
- dataset_id: `d03bf545-5269-4e80-945f-49e8552558f5`
- rows: **16068** (15m source bars: 48292)
- model_id: `binance_paxgusdt_direction_logistic_17813fb9`
- selected: `logistic`
- test accuracy: `0.44214` vs majority `0.431356` (Δ≈+0.011) — weak; research-only

Set `BINANCE_ML_MODEL_ID` to this model_id (optional; auto-resolves from `SELECTED_MODEL_ID.txt`).

```json
{
  "generated_at": "2026-08-12T11:43:29.902937+00:00",
  "symbol": "PAXGUSDT",
  "research_track": "binance_paxgusdt",
  "dataset_id": "d03bf545-5269-4e80-945f-49e8552558f5",
  "row_count": 16068,
  "source_bars_15m": 48292,
  "class_distribution": {
    "counts": {
      "DOWN": 7145,
      "FLAT": 1643,
      "UP": 7280
    },
    "pct": {
      "DOWN": 0.4447,
      "FLAT": 0.1023,
      "UP": 0.4531
    },
    "n": 16068
  },
  "model_id": "binance_paxgusdt_direction_logistic_17813fb9",
  "selected_model_type": "logistic",
  "validation_metrics": {
    "accuracy": 0.380498,
    "balanced_accuracy": 0.388619,
    "precision_macro": 0.359991,
    "recall_macro": 0.388619,
    "f1_macro": 0.354985,
    "confusion_matrix": {
      "DOWN": {
        "DOWN": 343,
        "FLAT": 280,
        "UP": 460
      },
      "FLAT": {
        "DOWN": 68,
        "FLAT": 111,
        "UP": 91
      },
      "UP": {
        "DOWN": 357,
        "FLAT": 237,
        "UP": 463
      }
    },
    "support": {
      "DOWN": 1083,
      "UP": 1057,
      "FLAT": 270
    },
    "n": 2410
  },
  "test_metrics": {
    "accuracy": 0.44214,
    "balanced_accuracy": 0.412703,
    "precision_macro": 0.402787,
    "recall_macro": 0.412703,
    "f1_macro": 0.399821,
    "confusion_matrix": {
      "DOWN": {
        "DOWN": 391,
        "FLAT": 147,
        "UP": 551
      },
      "FLAT": {
        "DOWN": 63,
        "FLAT": 89,
        "UP": 130
      },
      "UP": {
        "DOWN": 313,
        "FLAT": 141,
        "UP": 586
      }
    },
    "support": {
      "DOWN": 1089,
      "UP": 1040,
      "FLAT": 282
    },
    "n": 2411
  },
  "majority_baseline_test": {
    "accuracy": 0.431356,
    "balanced_accuracy": 0.333333,
    "precision_macro": 0.143785,
    "recall_macro": 0.333333,
    "f1_macro": 0.200908,
    "confusion_matrix": {
      "DOWN": {
        "DOWN": 0,
        "FLAT": 0,
        "UP": 1089
      },
      "FLAT": {
        "DOWN": 0,
        "FLAT": 0,
        "UP": 282
      },
      "UP": {
        "DOWN": 0,
        "FLAT": 0,
        "UP": 1040
      }
    },
    "support": {
      "DOWN": 1089,
      "UP": 1040,
      "FLAT": 282
    },
    "n": 2411
  },
  "skill_vs_majority_acc": 0.01078399999999996,
  "disclaimer": "Research suggestion model only. Not Delta PAXGUSD. Not Phase 6/10 GO. Not Phase 12.",
  "phase_6_10_untouched": true
}
```
