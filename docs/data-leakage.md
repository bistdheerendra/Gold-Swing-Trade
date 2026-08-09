# Data Leakage Prevention

## Absolute rule

At row timestamp **T**:

- Features use bars / events with time ≤ T (and HTF closed; SMC `confirm_index ≤ index`)
- Labels use bars / outcomes with time > T

## Tests

1. Mutate future bars → features at T unchanged  
2. Mutate future bars → labels at T may change  
3. Forbidden feature keys (`future_*`, `strategy_outcome`, trade results) rejected by validator  
4. Chronological split with no train/val/test contamination  

## Audit

`GET /api/ml/dataset/{id}/audit?timestamp=` reports latest source candle, HTF candles, SMC event, strategy state used for that row.

## Not done in Phase 8

Fitting scalers on full data, SMOTE, feature selection using test labels, model training.
