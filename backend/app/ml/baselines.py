"""Baselines for research comparison — not production signals."""

from __future__ import annotations

from collections import Counter
from typing import Any, List, Sequence

import numpy as np


def majority_predict(y_train: Sequence[Any], n: int) -> List[str]:
    yt = [str(x) for x in y_train]
    if not yt:
        return ["NEUTRAL"] * n
    maj = Counter(yt).most_common(1)[0][0]
    return [maj] * n


def random_predict(y_train: Sequence[Any], n: int, *, seed: int = 42) -> List[str]:
    yt = [str(x) for x in y_train]
    rng = np.random.default_rng(seed)
    classes = list(set(yt)) or ["NEUTRAL"]
    return [str(classes[i]) for i in rng.integers(0, len(classes), size=n)]


def strategy_score_threshold_accept(
    scores: Sequence[Any], *, threshold: float = 65.0
) -> List[bool]:
    out = []
    for s in scores:
        try:
            out.append(float(s) >= threshold)
        except (TypeError, ValueError):
            out.append(False)
    return out
