"""Chronological dataset splits — never shuffle."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from app.ml.schemas import DatasetRow, DatasetSplitSizes


def chronological_split(
    rows: Sequence[DatasetRow],
    *,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> Tuple[List[DatasetRow], List[DatasetRow], List[DatasetRow], DatasetSplitSizes]:
    n = len(rows)
    if n == 0:
        return [], [], [], DatasetSplitSizes(train=0, validation=0, test=0, total=0)
    t_end = int(n * train_ratio)
    v_end = int(n * (train_ratio + validation_ratio))
    t_end = max(1, min(t_end, max(1, n - 2))) if n > 2 else n
    v_end = max(t_end + 1, min(v_end, n - 1)) if n > 2 else n
    train = list(rows[:t_end])
    val = list(rows[t_end:v_end])
    test = list(rows[v_end:])
    return (
        train,
        val,
        test,
        DatasetSplitSizes(train=len(train), validation=len(val), test=len(test), total=n),
    )


def assert_no_split_contamination(
    train: Sequence[DatasetRow],
    val: Sequence[DatasetRow],
    test: Sequence[DatasetRow],
) -> None:
    if train and val and train[-1].timestamp >= val[0].timestamp:
        raise ValueError("TRAIN/VALIDATION chronological contamination")
    if val and test and val[-1].timestamp >= test[0].timestamp:
        raise ValueError("VALIDATION/TEST chronological contamination")
    if train and test and not val and train[-1].timestamp >= test[0].timestamp:
        raise ValueError("TRAIN/TEST chronological contamination")
