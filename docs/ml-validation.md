# ML Validation (Phase 9)

## Chronological splits

Inherited from Phase 8 (example 70 / 15 / 15). Random train/test splits are forbidden.

## Metrics

**Classification:** accuracy, balanced_accuracy, precision/recall/F1 macro, confusion matrix.

**Regression:** MAE, RMSE, R², directional (sign) accuracy.

**Trading (Rule vs Rule+ML):** trades, win rate, profit factor, expectancy R, net R, max drawdown R, streaks — using Phase 7 R outcomes (`future_R`), not a new simulator.

## Walk-forward architecture

Expanding chronological folds are documented for future use. Phase 9 does not run a large optimizer over folds.

## Calibration

Brier score, log loss, and probability buckets on **validation** only. Raw probabilities are not labeled “win probability” until calibrated.

## Overfitting

If train score ≫ validation score → flag `POSSIBLE_OVERFIT` (investigation, not auto-reject).

## Leakage guards

- Future labels never enter features
- Preprocessing fit on TRAIN only
- Model / threshold selection on VALIDATION only
- Mutating TEST labels must not change TRAIN-fit artifacts or selection
