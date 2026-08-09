"""Dataset descriptive statistics (no optimization)."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Dict, List, Optional, Sequence

from app.ml.schemas import ClassCount, DatasetRow, DatasetStatistics


def compute_statistics(rows: Sequence[DatasetRow]) -> DatasetStatistics:
    if not rows:
        return DatasetStatistics(row_count=0, feature_count=0, label_count=0)

    feature_keys = sorted({k for r in rows for k in r.features.keys()})
    label_keys = sorted({k for r in rows for k in r.labels.keys()})

    missing: Dict[str, float] = {}
    for k in feature_keys:
        miss = sum(1 for r in rows if r.features.get(k) is None)
        missing[k] = round(miss / len(rows), 6)

    summary: Dict[str, Dict[str, Optional[float]]] = {}
    for k in feature_keys:
        vals = []
        for r in rows:
            v = r.features.get(k)
            if isinstance(v, (int, float)) and v is not None:
                vals.append(float(v))
        if not vals:
            summary[k] = {
                "count": 0,
                "min": None,
                "max": None,
                "mean": None,
                "median": None,
                "std": None,
                "unique": 0,
            }
            continue
        vals_sorted = sorted(vals)
        mean = sum(vals) / len(vals)
        var = sum((x - mean) ** 2 for x in vals) / len(vals)
        mid = len(vals_sorted) // 2
        median = (
            vals_sorted[mid]
            if len(vals_sorted) % 2
            else (vals_sorted[mid - 1] + vals_sorted[mid]) / 2
        )
        summary[k] = {
            "count": float(len(vals)),
            "min": vals_sorted[0],
            "max": vals_sorted[-1],
            "mean": mean,
            "median": median,
            "std": var**0.5,
            "unique": float(len(set(vals))),
        }

    class_dist: Dict[str, List[ClassCount]] = {}
    for label_key in ("direction", "strategy_outcome", "multiclass_outcome"):
        if label_key not in label_keys:
            continue
        c = Counter(str(r.labels.get(label_key)) for r in rows if r.labels.get(label_key) is not None)
        total = sum(c.values()) or 1
        class_dist[label_key] = [
            ClassCount(key=k, count=v, percentage=round(v / total, 6))
            for k, v in sorted(c.items())
        ]

    return DatasetStatistics(
        row_count=len(rows),
        feature_count=len(feature_keys),
        label_count=len(label_keys),
        missing_by_feature=missing,
        class_distribution=class_dist,
        feature_summary=summary,
    )
