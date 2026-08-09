"""Factory for research models."""

from __future__ import annotations

from typing import List

from app.ml.models.base import BaseModel
from app.ml.models.gradient_boosting import GradientBoostingModel
from app.ml.models.logistic import LogisticModel
from app.ml.models.random_forest import RandomForestModel


def list_model_types() -> List[str]:
    return ["logistic", "random_forest", "gradient_boosting"]


def create_model(model_type: str, *, task: str = "classification", **kwargs) -> BaseModel:
    mt = model_type.lower().strip()
    if mt in ("logistic", "logistic_regression"):
        return LogisticModel(task=task, **kwargs)
    if mt in ("random_forest", "rf"):
        return RandomForestModel(task=task, **kwargs)
    if mt in ("gradient_boosting", "gb", "hgb"):
        return GradientBoostingModel(task=task, **kwargs)
    raise ValueError(f"Unknown model_type: {model_type}. Allowed: {list_model_types()}")
