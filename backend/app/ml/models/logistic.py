"""Logistic regression baseline (interpretable)."""

from __future__ import annotations

from typing import Dict, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

from app.ml.models.base import BaseModel


class LogisticModel(BaseModel):
    model_type = "logistic"

    def __init__(self, *, task: str = "classification", **kwargs) -> None:
        super().__init__(**kwargs)
        self.task = task

    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: Sequence[str]) -> "LogisticModel":
        self.feature_names_ = list(feature_names)
        if self.task == "regression":
            self._model = Ridge(random_state=self.random_seed)
            self._model.fit(X, y.astype(float))
            self.classes_ = None
        else:
            self._model = LogisticRegression(
                max_iter=1000,
                random_state=self.random_seed,
                class_weight=self.class_weight,
            )
            self._model.fit(X, y.astype(str))
            self.classes_ = [str(c) for c in self._model.classes_]
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self._model is not None
        return self._model.predict(X)

    def feature_importance(self) -> Dict[str, float]:
        if self._model is None or not hasattr(self._model, "coef_"):
            return {}
        coef = np.asarray(self._model.coef_)
        if coef.ndim > 1:
            mag = np.mean(np.abs(coef), axis=0)
        else:
            mag = np.abs(coef)
        return {n: float(v) for n, v in zip(self.feature_names_, mag)}
