# ML Models (Phase 9)

Common interface (`fit`, `predict`, `predict_proba`, `evaluate`, `save`, `load`):

| Type | Implementation | Role |
|------|----------------|------|
| `logistic` | sklearn `LogisticRegression` / `Ridge` | Interpretable baseline |
| `random_forest` | sklearn RF | Non-linear baseline |
| `gradient_boosting` | sklearn `HistGradientBoosting*` | Lightweight boosting |

Factory: `app.ml.models.registry.create_model`.

Defaults are small and documented. **No** GridSearch / Optuna / deep learning in Phase 9.

Feature importance:

- Trees: impurity importances
- Logistic / Ridge: coefficient magnitude (+ signed tops for explainability)

Models are versioned (`model_version`) with dataset / feature / label / preprocessing versions in registry metadata.
