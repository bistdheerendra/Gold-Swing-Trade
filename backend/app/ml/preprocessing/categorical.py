"""Categorical / boolean handling (deterministic codes)."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence


def fit_category_map(values: Sequence[Any]) -> Dict[str, int]:
    """Map seen TRAIN categories to stable integer codes; unseen → 0."""
    mapping: Dict[str, int] = {"__MISSING__": 0}
    next_id = 1
    for v in values:
        key = "__MISSING__" if v is None or v == "" else str(v)
        if key not in mapping:
            mapping[key] = next_id
            next_id += 1
    return mapping


def encode_category(value: Any, mapping: Dict[str, int]) -> int:
    key = "__MISSING__" if value is None or value == "" else str(value)
    return int(mapping.get(key, 0))


def boolean_to_float(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return 1.0 if float(value) != 0.0 else 0.0
    except (TypeError, ValueError):
        s = str(value).lower()
        if s in ("true", "1", "yes"):
            return 1.0
        return 0.0
