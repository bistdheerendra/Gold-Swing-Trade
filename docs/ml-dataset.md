# ML Dataset (Phase 8)

**Status:** Complete  
**Scope:** Leakage-free feature + label engineering only. **No model training.**

## Rule

```
FEATURE  = information available at timestamp T (past/present)
LABEL    = outcome after T (future only)
```

## Package

`backend/app/ml/` — feature_builder, label_builder, dataset_builder, validator, split, exporter, statistics

## Versions

- `dataset_version` 1.0.0  
- `feature_version` 1.0.0  
- `label_version` 1.0.0  
- `strategy_version` (from settings)

## Outputs

Under `data/ml_datasets/{dataset_id}/`:

- `all.csv`, `train.csv`, `validation.csv`, `test.csv`  
- `dataset_metadata.json`  
- optional `all.parquet` if pandas parquet available  

## Split

Chronological 70 / 15 / 15 — never shuffled. Scalers belong in Phase 9 (fit on TRAIN only).

## API

- `POST /api/ml/dataset/build`  
- `GET /api/ml/dataset/{id}`  
- `GET /api/ml/dataset/{id}/stats`  
- `GET /api/ml/dataset/{id}/audit?timestamp=`  

## UI

Dashboard → **ML Dataset** page.

See also: [ml-features.md](ml-features.md), [ml-labels.md](ml-labels.md), [data-leakage.md](data-leakage.md)
