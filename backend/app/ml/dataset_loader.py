"""Load Phase 8 CSV splits with feature/label separation."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class LoadedSplit:
    name: str
    rows: List[Dict[str, Any]] = field(default_factory=list)
    feature_names: List[str] = field(default_factory=list)
    label_names: List[str] = field(default_factory=list)
    timestamps: List[str] = field(default_factory=list)


@dataclass
class LoadedDataset:
    dataset_id: str
    root: Path
    train: LoadedSplit
    validation: LoadedSplit
    test: LoadedSplit
    feature_names: List[str]
    label_names: List[str]


FORBIDDEN_FEATURE_PREFIXES = ("y_", "future_")
FORBIDDEN_FEATURE_KEYS = {
    "strategy_outcome",
    "future_R",
    "trade_result",
    "tp_hit",
    "sl_hit",
}


class DatasetLoader:
    def load(self, dataset_dir: str | Path, dataset_id: Optional[str] = None) -> LoadedDataset:
        root = Path(dataset_dir)
        if not root.exists():
            raise FileNotFoundError(f"Dataset dir not found: {root}")
        train = self._load_csv(root / "train.csv", "train")
        val = self._load_csv(root / "validation.csv", "validation")
        test = self._load_csv(root / "test.csv", "test")
        feature_names = train.feature_names or val.feature_names or test.feature_names
        label_names = train.label_names or val.label_names or test.label_names
        self._assert_no_leakage(feature_names)
        return LoadedDataset(
            dataset_id=dataset_id or root.name,
            root=root,
            train=train,
            validation=val,
            test=test,
            feature_names=feature_names,
            label_names=label_names,
        )

    def _load_csv(self, path: Path, name: str) -> LoadedSplit:
        if not path.exists():
            raise FileNotFoundError(f"Missing split file: {path}")
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows_raw = list(reader)
        feature_names = [c[2:] for c in (reader.fieldnames or []) if c.startswith("f_")]
        label_names = [c[2:] for c in (reader.fieldnames or []) if c.startswith("y_")]
        rows: List[Dict[str, Any]] = []
        timestamps: List[str] = []
        for raw in rows_raw:
            feat = {k[2:]: _parse_val(raw.get(k)) for k in raw if k.startswith("f_")}
            labels = {k[2:]: _parse_val(raw.get(k)) for k in raw if k.startswith("y_")}
            rows.append({"features": feat, "labels": labels, "timestamp": raw.get("timestamp")})
            timestamps.append(str(raw.get("timestamp") or ""))
        # flatten features for preprocessing convenience
        flat_rows = []
        for r in rows:
            item = dict(r["features"])
            item["__timestamp"] = r["timestamp"]
            item["__labels"] = r["labels"]
            flat_rows.append(item)
        return LoadedSplit(
            name=name,
            rows=flat_rows,
            feature_names=feature_names,
            label_names=label_names,
            timestamps=timestamps,
        )

    def _assert_no_leakage(self, feature_names: Sequence[str]) -> None:
        for n in feature_names:
            if n in FORBIDDEN_FEATURE_KEYS or n.startswith("future_"):
                raise ValueError(f"Leaky feature detected in dataset: {n}")


def _parse_val(v: Optional[str]) -> Any:
    if v is None or v == "":
        return None
    try:
        if "." in v or "e" in v.lower():
            return float(v)
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def extract_xy(
    split: LoadedSplit, feature_names: Sequence[str], target: str
) -> tuple[List[Dict[str, Any]], List[Any], List[str]]:
    X_rows = []
    y = []
    ts = []
    for row in split.rows:
        labels = row.get("__labels") or {}
        if target not in labels or labels[target] is None or labels[target] == "":
            continue
        X_rows.append({k: row.get(k) for k in feature_names})
        y.append(labels[target])
        ts.append(str(row.get("__timestamp") or ""))
    return X_rows, y, ts
