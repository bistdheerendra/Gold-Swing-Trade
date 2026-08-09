"""Deterministic missing-value imputation helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence


def median_impute(value: Any, median: float) -> float:
    if value is None or value == "":
        return float(median)
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(median)
    if v != v:  # NaN
        return float(median)
    return v


def mode_or_unknown(value: Any, *, unknown: str = "__MISSING__") -> str:
    if value is None or value == "":
        return unknown
    return str(value)


def drop_rows_with_missing(
    rows: Sequence[Dict[str, Any]],
    feature_names: Sequence[str],
    *,
    enabled: bool = False,
) -> list:
    """Only drop when explicitly configured — default is impute, never silent drop."""
    if not enabled:
        return list(rows)
    out = []
    for r in rows:
        if all(r.get(n) is not None and r.get(n) != "" for n in feature_names):
            out.append(r)
    return out
