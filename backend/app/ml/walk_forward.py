"""Walk-forward validation architecture (expanding train windows)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class WalkForwardFold:
    fold_id: int
    train_start: int
    train_end: int  # exclusive
    validation_start: int
    validation_end: int  # exclusive
    description: str


def build_expanding_folds(
    n_rows: int,
    *,
    n_folds: int = 3,
    min_train: int = 50,
    val_fraction: float = 0.15,
) -> List[WalkForwardFold]:
    """
    Chronological expanding folds. Does NOT use TEST.

    Fold k: train = [0, train_end_k), validation = [train_end_k, val_end_k)
    """
    if n_rows < min_train + 10 or n_folds < 1:
        return []
    folds: List[WalkForwardFold] = []
    # Reserve last val_fraction * remaining for progressive slices
    usable = n_rows
    val_size = max(10, int(usable * val_fraction / n_folds))
    # Place n_folds validation windows near the end of TRAIN+VAL region
    # Assume caller passes only TRAIN+VALIDATION concatenated length
    for k in range(n_folds):
        val_end = usable - (n_folds - 1 - k) * val_size
        val_start = val_end - val_size
        train_end = val_start
        if train_end < min_train or val_start <= 0:
            continue
        folds.append(
            WalkForwardFold(
                fold_id=k + 1,
                train_start=0,
                train_end=train_end,
                validation_start=val_start,
                validation_end=val_end,
                description=(
                    f"Fold {k + 1}: Train[0:{train_end}) → Validation[{val_start}:{val_end})"
                ),
            )
        )
    return folds


def document_folds(folds: Sequence[WalkForwardFold]) -> List[dict]:
    return [
        {
            "fold_id": f.fold_id,
            "train_start": f.train_start,
            "train_end": f.train_end,
            "validation_start": f.validation_start,
            "validation_end": f.validation_end,
            "description": f.description,
        }
        for f in folds
    ]
