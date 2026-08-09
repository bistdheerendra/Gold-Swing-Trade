"""Numeric / categorical preprocessing — TRAIN-fit only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from app.ml.preprocessing.schema import FeatureTypeSchema, infer_feature_schema


class PreprocessingPipeline:
    version: str = "1.0.0"

    def __init__(self, schema: Optional[FeatureTypeSchema] = None) -> None:
        self.schema = schema
        self.feature_names_: List[str] = []
        self.medians_: Dict[str, float] = {}
        self.means_: Dict[str, float] = {}
        self.stds_: Dict[str, float] = {}
        self.fitted_ = False

    def fit(self, rows: Sequence[Dict[str, Any]], feature_names: Sequence[str]) -> "PreprocessingPipeline":
        self.feature_names_ = list(feature_names)
        self.schema = self.schema or infer_feature_schema(feature_names)
        for name in self.feature_names_:
            vals = []
            for r in rows:
                v = r.get(name)
                if v is None or v == "":
                    continue
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    continue
            if vals:
                arr = np.asarray(vals, dtype=float)
                self.medians_[name] = float(np.median(arr))
                self.means_[name] = float(np.mean(arr))
                std = float(np.std(arr))
                self.stds_[name] = std if std > 1e-12 else 1.0
            else:
                self.medians_[name] = 0.0
                self.means_[name] = 0.0
                self.stds_[name] = 1.0
        self.fitted_ = True
        return self

    def transform(self, rows: Sequence[Dict[str, Any]]) -> Tuple[np.ndarray, List[str]]:
        if not self.fitted_:
            raise RuntimeError("PreprocessingPipeline must be fit on TRAIN before transform")
        X = []
        for r in rows:
            vec = []
            for name in self.feature_names_:
                v = r.get(name)
                if v is None or v == "":
                    val = self.medians_.get(name, 0.0)
                else:
                    try:
                        val = float(v)
                    except (TypeError, ValueError):
                        val = self.medians_.get(name, 0.0)
                if not np.isfinite(val):
                    val = self.medians_.get(name, 0.0)
                # standardize numeric; leave boolean/categorical as raw imputed
                if self.schema and name in self.schema.numeric:
                    mean = self.means_.get(name, 0.0)
                    std = self.stds_.get(name, 1.0)
                    val = (val - mean) / std
                vec.append(val)
            X.append(vec)
        return np.asarray(X, dtype=float), list(self.feature_names_)

    def fit_transform(
        self, rows: Sequence[Dict[str, Any]], feature_names: Sequence[str]
    ) -> Tuple[np.ndarray, List[str]]:
        self.fit(rows, feature_names)
        return self.transform(rows)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.version,
            "feature_names": self.feature_names_,
            "schema": self.schema.model_dump() if self.schema else None,
            "medians": self.medians_,
            "means": self.means_,
            "stds": self.stds_,
            "fitted": self.fitted_,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self, path: Path) -> "PreprocessingPipeline":
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.feature_names_ = payload["feature_names"]
        self.schema = FeatureTypeSchema(**payload["schema"]) if payload.get("schema") else None
        self.medians_ = {k: float(v) for k, v in payload["medians"].items()}
        self.means_ = {k: float(v) for k, v in payload["means"].items()}
        self.stds_ = {k: float(v) for k, v in payload["stds"].items()}
        self.fitted_ = bool(payload.get("fitted"))
        return self
