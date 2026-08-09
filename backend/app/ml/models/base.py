"""Phase 9 model interface and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence

import numpy as np


class BaseModel(ABC):
    model_type: str = "base"
    task: str = "classification"  # classification | regression

    def __init__(self, *, random_seed: int = 42, class_weight: Optional[str] = "balanced") -> None:
        self.random_seed = random_seed
        self.class_weight = class_weight
        self._model: Any = None
        self.classes_: Optional[List[str]] = None
        self.feature_names_: List[str] = []

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray, feature_names: Sequence[str]) -> "BaseModel":
        ...

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        ...

    def predict_proba(self, X: np.ndarray) -> Optional[np.ndarray]:
        if self._model is None or not hasattr(self._model, "predict_proba"):
            return None
        return self._model.predict_proba(X)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Compute task metrics for a held-out matrix."""
        from app.ml.training_metrics import classification_metrics, regression_metrics

        pred = self.predict(X)
        if self.task == "regression":
            return regression_metrics(y.astype(float), pred.astype(float))
        return classification_metrics(y, pred)

    def feature_importance(self) -> Dict[str, float]:
        return {}

    def get_params(self) -> Dict[str, Any]:
        return {"random_seed": self.random_seed, "class_weight": self.class_weight}

    def save(self, path: str) -> None:
        import joblib

        joblib.dump(
            {
                "model_type": self.model_type,
                "task": self.task,
                "model": self._model,
                "classes_": self.classes_,
                "feature_names_": self.feature_names_,
                "params": self.get_params(),
            },
            path,
        )

    def load(self, path: str) -> "BaseModel":
        import joblib

        payload = joblib.load(path)
        self._model = payload["model"]
        self.classes_ = payload.get("classes_")
        self.feature_names_ = payload.get("feature_names_") or []
        return self
