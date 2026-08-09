"""Random Forest model."""

from __future__ import annotations

from typing import Dict, Sequence

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

from app.ml.models.base import BaseModel


class RandomForestModel(BaseModel):
    model_type = "random_forest"

    def __init__(self, *, task: str = "classification", n_estimators: int = 100, **kwargs) -> None:
        super().__init__(**kwargs)
        self.task = task
        self.n_estimators = n_estimators

    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: Sequence[str]) -> "RandomForestModel":
        self.feature_names_ = list(feature_names)
        if self.task == "regression":
            self._model = RandomForestRegressor(
                n_estimators=self.n_estimators,
                random_state=self.random_seed,
                n_jobs=-1,
            )
            self._model.fit(X, y.astype(float))
            self.classes_ = None
        else:
            self._model = RandomForestClassifier(
                n_estimators=self.n_estimators,
                random_state=self.random_seed,
                class_weight=self.class_weight,
                n_jobs=-1,
            )
            self._model.fit(X, y.astype(str))
            self.classes_ = [str(c) for c in self._model.classes_]
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        assert self._model is not None
        return self._model.predict(X)

    def feature_importance(self) -> Dict[str, float]:
        if self._model is None or not hasattr(self._model, "feature_importances_"):
            return {}
        return {
            n: float(v)
            for n, v in zip(self.feature_names_, self._model.feature_importances_)
        }

    def get_params(self) -> Dict:
        p = super().get_params()
        p["n_estimators"] = self.n_estimators
        return p
