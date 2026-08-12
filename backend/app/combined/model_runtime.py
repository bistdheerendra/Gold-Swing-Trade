"""Load Phase 9 artifacts for inference — transform only, never fit."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from app.ml.model_registry import get_model, list_models
from app.ml.models.registry import create_model
from app.ml.preprocessing.pipeline import PreprocessingPipeline


@dataclass
class LoadedRuntimeModel:
    model_id: str
    model_type: str
    target: str
    task: str
    model: Any
    pipeline: PreprocessingPipeline
    feature_names: List[str]
    meta: Dict[str, Any]
    model_version: str
    feature_version: str
    label_version: str
    dataset_version: str
    preprocessing_version: str
    selected_threshold: float
    probability_calibrated: bool = False


class ModelCompatibilityError(Exception):
    pass


class ModelUnavailableError(Exception):
    pass


def resolve_model_meta(model_id: Optional[str] = None) -> Dict[str, Any]:
    if model_id:
        meta = get_model(model_id)
        if meta is None:
            # try disk registry_entry under artifacts
            disk = _find_artifact_meta(model_id)
            if disk is None:
                raise ModelUnavailableError(f"Unknown model_id: {model_id}")
            return disk
        return meta
    models = list_models()
    if not models:
        # scan artifacts/ml for latest metrics.json
        found = _scan_latest_artifact()
        if found is None:
            raise ModelUnavailableError("No registered research models available")
        return found
    # Prefer strategy_outcome, else direction
    preferred = [m for m in models if m.get("target") == "strategy_outcome"]
    pool = preferred or models
    return sorted(pool, key=lambda m: m.get("trained_at") or "", reverse=True)[0]


def load_runtime_model(
    model_id: Optional[str] = None,
    *,
    expected_feature_version: str = "1.0.0",
) -> LoadedRuntimeModel:
    meta = resolve_model_meta(model_id)
    art = Path(meta.get("artifact_dir") or "")
    if not art.exists():
        raise ModelUnavailableError(f"Artifact dir missing: {art}")

    model_path = art / "model.joblib"
    prep_path = art / "preprocessing.json"
    schema_path = art / "feature_schema.json"
    if not model_path.exists() or not prep_path.exists():
        raise ModelUnavailableError("model.joblib or preprocessing.json missing")

    feature_version = str(meta.get("feature_version") or "1.0.0")
    if feature_version != expected_feature_version:
        raise ModelCompatibilityError(
            f"feature_version mismatch: model={feature_version} expected={expected_feature_version}"
        )

    pipe = PreprocessingPipeline().load(prep_path)
    if not pipe.fitted_:
        raise ModelCompatibilityError("Preprocessing artifact is not fitted")

    feature_names = list(meta.get("feature_names") or pipe.feature_names_)
    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if schema.get("features"):
            if list(schema["features"]) != feature_names:
                # prefer training feature order from schema
                feature_names = list(schema["features"])

    # preprocessing feature order must match
    if pipe.feature_names_ and pipe.feature_names_ != feature_names:
        raise ModelCompatibilityError(
            "Preprocessing feature_names incompatible with model feature schema"
        )

    model = create_model(
        meta.get("model_type") or "logistic",
        task=meta.get("task") or "classification",
        random_seed=int(meta.get("random_seed") or 42),
    )
    model.load(str(model_path))
    if model.feature_names_ and list(model.feature_names_) != feature_names:
        raise ModelCompatibilityError("Loaded model feature_names incompatible with schema")

    return LoadedRuntimeModel(
        model_id=meta["model_id"],
        model_type=meta.get("model_type") or model.model_type,
        target=str(meta.get("target") or "direction"),
        task=str(meta.get("task") or "classification"),
        model=model,
        pipeline=pipe,
        feature_names=feature_names,
        meta=meta,
        model_version=str(meta.get("model_version") or "1.0.0"),
        feature_version=feature_version,
        label_version=str(meta.get("label_version") or "1.0.0"),
        dataset_version=str(meta.get("dataset_version") or "1.0.0"),
        preprocessing_version=str(
            meta.get("preprocessing_version") or pipe.version or "1.0.0"
        ),
        selected_threshold=float(meta.get("selected_threshold_from_validation") or 0.60),
        probability_calibrated=bool(meta.get("probability_calibrated", False)),
    )


def transform_features(
    runtime: LoadedRuntimeModel, feature_row: Dict[str, Any]
) -> np.ndarray:
    """TRANSFORM only — never fit."""
    row = {k: feature_row.get(k) for k in runtime.feature_names}
    X, _ = runtime.pipeline.transform([row])
    return X


def predict_ml(
    runtime: LoadedRuntimeModel,
    feature_row: Dict[str, Any],
    *,
    rule_direction: str,
) -> Tuple[str, float, Dict[str, Any]]:
    """
    Returns (ml_prediction BUY|SELL|NEUTRAL, confidence, detail).
    """
    X = transform_features(runtime, feature_row)
    pred_raw = runtime.model.predict(X)[0]
    proba = runtime.model.predict_proba(X)
    classes = list(runtime.model.classes_ or [])
    detail: Dict[str, Any] = {
        "raw_prediction": str(pred_raw),
        "classes": classes,
        "probability_calibrated": runtime.probability_calibrated,
    }

    target = runtime.target
    if target == "strategy_outcome" or (
        classes and set(classes) & {"WIN", "LOSS", "NO_SETUP", "NO_ENTRY"}
    ):
        conf, mapped = _map_strategy_outcome(pred_raw, proba, classes, rule_direction)
        detail["mapping"] = "strategy_outcome→direction"
        return mapped, conf, detail

    if target == "direction" or (
        classes and set(c.upper() for c in classes) & {"UP", "DOWN", "NEUTRAL"}
    ):
        conf, mapped = _map_direction(pred_raw, proba, classes)
        detail["mapping"] = "direction→BUY/SELL/NEUTRAL"
        return mapped, conf, detail

    if target == "multiclass_outcome":
        conf, mapped = _map_multiclass(pred_raw, proba, classes, rule_direction)
        detail["mapping"] = "multiclass_outcome"
        return mapped, conf, detail

    # fallback: treat raw as class; confidence = max proba
    conf = float(np.max(proba[0])) if proba is not None else 0.5
    return "NEUTRAL", conf, detail


def _map_strategy_outcome(
    pred_raw: Any, proba: Optional[np.ndarray], classes: Sequence[str], rule_direction: str
) -> Tuple[float, str]:
    classes = list(classes)
    p_win = 0.0
    if proba is not None and "WIN" in classes:
        p_win = float(proba[0, classes.index("WIN")])
    elif str(pred_raw) == "WIN":
        p_win = 0.7
    pred = str(pred_raw).upper()
    if pred == "WIN":
        mapped = rule_direction if rule_direction in ("BUY", "SELL") else "NEUTRAL"
        return p_win if p_win > 0 else 0.6, mapped
    if pred == "LOSS":
        # conflict with rule setup quality
        opposite = "SELL" if rule_direction == "BUY" else "BUY" if rule_direction == "SELL" else "NEUTRAL"
        conf = 1.0 - p_win if p_win > 0 else (float(np.max(proba[0])) if proba is not None else 0.6)
        return conf, opposite
    return (float(np.max(proba[0])) if proba is not None else 0.5), "NEUTRAL"


def _map_direction(
    pred_raw: Any, proba: Optional[np.ndarray], classes: Sequence[str]
) -> Tuple[float, str]:
    orig = [str(c) for c in classes]
    pred = str(pred_raw).upper()
    mapping = {
        "UP": "BUY",
        "DOWN": "SELL",
        "NEUTRAL": "NEUTRAL",
        "FLAT": "NEUTRAL",
        "BUY": "BUY",
        "SELL": "SELL",
    }
    mapped = mapping.get(pred, "NEUTRAL")
    conf = 0.5
    if proba is not None and orig:
        try:
            idx = next(i for i, c in enumerate(orig) if str(c).upper() == pred)
            conf = float(proba[0, idx])
        except StopIteration:
            conf = float(np.max(proba[0]))
    return conf, mapped


def _map_multiclass(
    pred_raw: Any, proba: Optional[np.ndarray], classes: Sequence[str], rule_direction: str
) -> Tuple[float, str]:
    pred = str(pred_raw).upper()
    conf = float(np.max(proba[0])) if proba is not None else 0.5
    if "BUY_WIN" in pred:
        return conf, "BUY"
    if "SELL_WIN" in pred:
        return conf, "SELL"
    if "BUY_LOSS" in pred:
        return conf, "SELL" if rule_direction == "BUY" else "BUY"
    if "SELL_LOSS" in pred:
        return conf, "BUY" if rule_direction == "SELL" else "SELL"
    return conf, "NEUTRAL"


def _find_artifact_meta(model_id: str) -> Optional[Dict[str, Any]]:
    roots = [
        Path("artifacts/ml"),
        Path("artifacts/ml_candle"),
        Path("artifacts/ml_candle_binance"),
    ]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("metrics.json"):
            try:
                reg = path.parent / "registry_entry.json"
                if reg.exists():
                    meta = json.loads(reg.read_text(encoding="utf-8"))
                    if meta.get("model_id") == model_id:
                        meta["artifact_dir"] = str(path.parent)
                        return meta
                if path.parent.name == model_id:
                    meta = json.loads(path.read_text(encoding="utf-8"))
                    meta.setdefault("model_id", model_id)
                    meta["artifact_dir"] = str(path.parent)
                    return meta
            except (OSError, json.JSONDecodeError, TypeError):
                continue
    return None


def _scan_latest_artifact() -> Optional[Dict[str, Any]]:
    root = Path("artifacts/ml")
    if not root.exists():
        return None
    best = None
    best_t = ""
    for path in root.rglob("metrics.json"):
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta.setdefault("artifact_dir", str(path.parent))
        t = str(meta.get("trained_at") or "")
        if t >= best_t:
            best_t = t
            best = meta
    return best
