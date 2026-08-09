# ML Training (Phase 9)

Research-only offline training and validation. **No live predictions. No broker execution.**

## Pipeline

1. Load Phase 8 chronological splits (`train.csv` / `validation.csv` / `test.csv`)
2. Fit preprocessing **on TRAIN only**
3. Transform validation / test (no refit)
4. Fit candidate models on TRAIN
5. Select model using **VALIDATION** metrics only
6. Evaluate selected model **once** on held-out TEST
7. Persist artifacts under `artifacts/ml/{target}/{model_id}/`

## Targets

| Target | Task |
|--------|------|
| `direction` | Multiclass UP / DOWN / NEUTRAL |
| `strategy_outcome` | WIN / LOSS / NO_ENTRY / NO_SETUP (+ trade-only WIN vs LOSS) |
| `multiclass_outcome` | BUY_WIN / BUY_LOSS / SELL_WIN / SELL_LOSS / NO_SETUP |
| `return_{5,10,20,40}` | Regression |
| `future_R` | Regression (Phase 7 execution R) |

## Selection rule

Never choose models or ML filter thresholds using TEST. TEST is reported after selection.

## Artifacts

- `model.joblib`
- `preprocessing.json`
- `feature_schema.json`
- `metrics.json`

Status is always `RESEARCH` in Phase 9.

## Phase 10 note

Trained artifacts are loaded by `CombinedSignalEngine` for inference (**transform only**). Thresholds selected on VALIDATION are frozen before TEST / combined backtests. See `docs/combined-signal-engine.md`.
