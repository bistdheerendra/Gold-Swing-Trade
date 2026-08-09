# ML + Strategy Integration (Phase 10)

## Architecture

Phase 6 remains the sole setup detector. Phase 9 models act as a **filter** on BUY/SELL setups using the same causal feature pipeline and TRAIN-fitted preprocessor (transform only).

## Versions checked

Before inference: `model_version`, `feature_version`, `label_version`, `dataset_version`, `preprocessing_version`, feature name order.

## Backtest modes

| Mode | Behavior |
|------|----------|
| `RULE_ONLY` | Phase 6 only |
| `ML_FILTER` / `COMBINED` | Phase 6 + ML filter (no retrain) |

Comparison endpoint reports losers avoided / winners rejected.

## Limitations

- Research / decision-support only
- Mock data can distort metrics
- Uncalibrated probabilities must not be sold as win odds
- No broker execution, sizing, or live orders in Phase 10
