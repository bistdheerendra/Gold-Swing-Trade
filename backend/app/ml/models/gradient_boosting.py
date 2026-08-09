"""Gradient Boosting (sklearn HistGradientBoosting — lightweight)."""

from __future__ import annotations

from typing import Dict, Sequence

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor

from app.ml.models.base import BaseModel


class GradientBoostingModel(BaseModel):
    model_type = "gradient_boosting"

    def __init__(self, *, task: str = "classification", max_iter: int = 100, **kwargs) -> None:
        # class_weight not supported the same way on HGB — keep for interface
        super().__init__(**kwargs)
        self.task = task
        self.max_iter = max_iter

    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: Sequence[str]) -> "GradientBoostingModel":
        self.feature_names_ = list(feature_names)
        if self.task == "regression":
            self._model = HistGradientBoostingRegressor(
                max_iter=self.max_iter,
                random_state=self.random_seed,
            )
            self._model.fit(X, y.astype(float))
            self.classes_ = None
        else:
            self._model = HistGradientBoostingClassifier(
                max_iter=self.max_iter,
                random_state=self.random_seed,
            )
            self._model.fit(X, y.astype(str))
            self.classes_ = [str(c) for c in self._model.classes_]
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self._model is not None
        return self._model.predict(X)

    def feature_importance(self) -> Dict[str, float]:
        # HGB has no native feature_importances_; return empty — permutation elsewhere
        return {}

    def get_params(self) -> Dict:
        p = super().get_params()
        p["max_iter"] = self.max_iter
        return p
