"""Numeric feature transforms (fit on TRAIN only)."""

from __future__ import annotations

from typing import Sequence

import numpy as np


def fit_standardize(values: Sequence[float]) -> tuple[float, float]:
    arr = np.asarray(list(values), dtype=float)
    if len(arr) == 0:
        return 0.0, 1.0
    mean = float(np.mean(arr))
    std = float(np.std(arr))
    return mean, std if std > 1e-12 else 1.0


def apply_standardize(value: float, mean: float, std: float) -> float:
    return (value - mean) / (std if std > 1e-12 else 1.0)
