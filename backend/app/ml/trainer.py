"""Train / validate / test research models (Phase 9)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from app.ml.baselines import majority_predict, random_predict, strategy_score_threshold_accept
from app.ml.combination import combine_rule_ml, scan_thresholds_on_validation
from app.ml.dataset_loader import DatasetLoader, LoadedDataset, extract_xy
from app.ml.models.registry import create_model, list_model_types
from app.ml.preprocessing.pipeline import PreprocessingPipeline
from app.ml.training_metrics import (
    calibration_buckets,
    classification_metrics,
    overfitting_flag,
    regression_metrics,
    trading_metrics_from_r,
)
from app.ml.walk_forward import build_expanding_folds, document_folds

CLASSIFICATION_TARGETS = {
    "direction",
    "strategy_outcome",
    "multiclass_outcome",
}
REGRESSION_TARGETS = {
    "return_5",
    "return_10",
    "return_20",
    "return_40",
    "future_R",
}


class ModelTrainer:
    def __init__(
        self,
        *,
        artifacts_root: str | Path = "artifacts/ml",
        random_seed: int = 42,
        model_version: str = "1.0.0",
    ) -> None:
        self.artifacts_root = Path(artifacts_root)
        self.random_seed = random_seed
        self.model_version = model_version

    def train(
        self,
        dataset: LoadedDataset,
        *,
        target: str,
        model_types: Optional[Sequence[str]] = None,
        run_test: bool = True,
        model_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        task = _infer_task(target, dataset.label_names)
        types = [model_type] if model_type else list(model_types or list_model_types())

        X_train_rows, y_train, ts_train = extract_xy(
            dataset.train, dataset.feature_names, target
        )
        X_val_rows, y_val, ts_val = extract_xy(
            dataset.validation, dataset.feature_names, target
        )
        X_test_rows, y_test, ts_test = extract_xy(
            dataset.test, dataset.feature_names, target
        )
        if len(X_train_rows) < 10:
            raise ValueError(f"Insufficient TRAIN rows for target={target}: {len(X_train_rows)}")

        class_counts = _class_counts(y_train) if task == "classification" else {}

        pipe = PreprocessingPipeline()
        X_train, feat_names = pipe.fit_transform(X_train_rows, dataset.feature_names)
        X_val, _ = (
            pipe.transform(X_val_rows)
            if X_val_rows
            else (np.empty((0, X_train.shape[1])), feat_names)
        )
        X_test, _ = (
            pipe.transform(X_test_rows)
            if X_test_rows
            else (np.empty((0, X_train.shape[1])), feat_names)
        )

        y_train_arr = np.asarray(y_train)
        y_val_arr = np.asarray(y_val) if y_val else np.asarray([])
        y_test_arr = np.asarray(y_test) if y_test else np.asarray([])

        # Walk-forward architecture (documented boundaries; not a hyper-optimizer)
        wf_folds = build_expanding_folds(len(X_train_rows) + len(X_val_rows), n_folds=3)

        candidates: List[Dict[str, Any]] = []
        fit_errors: List[str] = []
        for mt in types:
            try:
                model = create_model(mt, task=task, random_seed=self.random_seed)
                model.fit(X_train, y_train_arr, feat_names)
            except Exception as exc:  # noqa: BLE001
                fit_errors.append(f"{mt}: {exc}")
                continue
            train_pred = model.predict(X_train)
            val_pred = model.predict(X_val) if len(X_val) else np.asarray([])
            train_m = _eval(task, y_train_arr, train_pred)
            val_m = _eval(task, y_val_arr, val_pred) if len(y_val_arr) else {}
            score = _selection_score(task, val_m, train_m)
            candidates.append(
                {
                    "model_type": mt,
                    "model": model,
                    "train_metrics": train_m,
                    "validation_metrics": val_m,
                    "selection_score": score,
                    "feature_importance": model.feature_importance(),
                }
            )

        if not candidates:
            raise ValueError(
                "No models trained successfully for target="
                f"{target}. Class counts={class_counts}. Errors={fit_errors}"
            )

        # Select on VALIDATION only
        candidates.sort(key=lambda c: c["selection_score"], reverse=True)
        best = candidates[0]
        selected = best["model"]

        # Trade-only WIN vs LOSS (strategy_outcome)
        trade_only: Dict[str, Any] = {}
        if target == "strategy_outcome" and len(y_val_arr):
            trade_only["validation"] = _trade_only_eval(y_val_arr, selected.predict(X_val))

        # Baselines on validation
        baselines: Dict[str, Any] = {}
        if task == "classification" and len(y_val_arr):
            maj = majority_predict(y_train_arr, len(y_val_arr))
            rnd = random_predict(y_train_arr, len(y_val_arr), seed=self.random_seed)
            baselines["majority_validation"] = classification_metrics(y_val_arr, maj)
            baselines["random_validation"] = classification_metrics(y_val_arr, rnd)
            if target == "strategy_outcome":
                baselines["phase6_outcome_distribution"] = class_counts
                scores = [_feature_from_ts(dataset.validation.rows, t, "strategy_score") for t in ts_val]
                accept = strategy_score_threshold_accept(scores, threshold=65.0)
                # Baseline 4: score>=65 → predict WIN else LOSS/NO_SETUP heuristic
                score_preds = [
                    "WIN" if a and str(o) in ("WIN", "LOSS") else str(o)
                    for a, o in zip(accept, y_val)
                ]
                baselines["strategy_score_threshold_65_validation"] = classification_metrics(
                    y_val_arr, score_preds
                )

        # Calibration research on validation
        calibration: Dict[str, Any] = {}
        val_proba = selected.predict_proba(X_val) if len(X_val) else None
        if task == "classification" and val_proba is not None and selected.classes_:
            pos = "WIN" if "WIN" in selected.classes_ else selected.classes_[-1]
            calibration = calibration_buckets(
                y_val_arr, val_proba, selected.classes_, positive_class=pos
            )

        # Threshold scan on VALIDATION for strategy_outcome
        filter_research: Dict[str, Any] = {}
        selected_threshold = 0.60
        if target == "strategy_outcome" and val_proba is not None and selected.classes_:
            dirs_aligned, outcomes_aligned, future_r_aligned = [], list(y_val), []
            for tstamp in ts_val:
                row = _find_row(dataset.validation.rows, tstamp)
                dirs_aligned.append(row.get("strategy_direction") if row else 0)
                fr = (row.get("__labels") or {}).get("future_R") if row else None
                future_r_aligned.append(fr)
            scan = scan_thresholds_on_validation(
                rule_directions=dirs_aligned,
                strategy_outcomes=outcomes_aligned,
                future_rs=future_r_aligned,
                ml_proba=val_proba,
                classes=selected.classes_,
                accept_class="WIN" if "WIN" in selected.classes_ else selected.classes_[-1],
            )
            selected_threshold = float(scan["selected_threshold"])
            filter_research["validation_scan"] = scan
            rule_rs: List[float] = []
            for tstamp, out in zip(ts_val, y_val):
                if str(out) not in ("WIN", "LOSS"):
                    continue
                row = _find_row(dataset.validation.rows, tstamp)
                if not row:
                    continue
                fr = (row.get("__labels") or {}).get("future_R")
                if fr is not None:
                    rule_rs.append(float(fr))
            filter_research["rule_only_validation"] = trading_metrics_from_r(rule_rs)

        # Held-out TEST once after selection
        test_metrics: Dict[str, Any] = {}
        test_filter: Dict[str, Any] = {}
        if run_test and len(X_test):
            test_pred = selected.predict(X_test)
            test_metrics = _eval(task, y_test_arr, test_pred)
            if target == "strategy_outcome":
                trade_only["test"] = _trade_only_eval(y_test_arr, test_pred)
            test_proba = selected.predict_proba(X_test)
            if target == "strategy_outcome" and test_proba is not None and selected.classes_:
                dirs_t, outcomes_t, fr_t = [], list(y_test), []
                for tstamp in ts_test:
                    row = _find_row(dataset.test.rows, tstamp)
                    dirs_t.append(row.get("strategy_direction") if row else 0)
                    fr_t.append((row.get("__labels") or {}).get("future_R") if row else None)
                test_filter = combine_rule_ml(
                    rule_directions=dirs_t,
                    strategy_outcomes=outcomes_t,
                    future_rs=fr_t,
                    ml_proba=test_proba,
                    classes=selected.classes_,
                    accept_class="WIN" if "WIN" in selected.classes_ else selected.classes_[-1],
                    threshold=selected_threshold,
                )

        train_score = _selection_score(task, best["train_metrics"], best["train_metrics"])
        val_score = best["selection_score"]
        test_score = (
            _selection_score(task, test_metrics, test_metrics) if test_metrics else None
        )
        overfit = overfitting_flag(
            _primary(task, best["train_metrics"]),
            _primary(task, best["validation_metrics"])
            if best["validation_metrics"]
            else 0.0,
        )

        model_id = f"{target}_{best['model_type']}_{uuid.uuid4().hex[:8]}"
        art_dir = self.artifacts_root / target / model_id
        art_dir.mkdir(parents=True, exist_ok=True)
        selected.save(str(art_dir / "model.joblib"))
        pipe.save(art_dir / "preprocessing.json")
        explain = _explainability(best["feature_importance"], selected)

        meta = {
            "model_id": model_id,
            "model_type": best["model_type"],
            "model_version": self.model_version,
            "dataset_id": dataset.dataset_id,
            "dataset_version": "1.0.0",
            "feature_version": "1.0.0",
            "label_version": "1.0.0",
            "feature_count": len(feat_names),
            "target": target,
            "task": task,
            "status": "RESEARCH",
            "random_seed": self.random_seed,
            "feature_names": feat_names,
            "preprocessing_version": pipe.version,
            "hyperparameters": selected.get_params(),
            "class_counts_train": class_counts,
            "candidates": [
                {
                    "model_type": c["model_type"],
                    "selection_score": c["selection_score"],
                    "train_metrics": c["train_metrics"],
                    "validation_metrics": c["validation_metrics"],
                }
                for c in candidates
            ],
            "selected_model_type": best["model_type"],
            "train_metrics": best["train_metrics"],
            "validation_metrics": best["validation_metrics"],
            "test_metrics": test_metrics,
            "trade_only_win_loss": trade_only,
            "baselines": baselines,
            "calibration_validation": calibration,
            "feature_importance": _top_features(best["feature_importance"], 20),
            "explainability": explain,
            "filter_research": filter_research,
            "test_filter": test_filter,
            "selected_threshold_from_validation": selected_threshold,
            "walk_forward_architecture": document_folds(wf_folds),
            "overfitting": overfit,
            "scores": {"train": train_score, "validation": val_score, "test": test_score},
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "artifact_dir": str(art_dir),
            "notes": [
                "RESEARCH ONLY — not production",
                "Model selection used VALIDATION only",
                "TEST evaluated once after selection",
                "Thresholds scanned on VALIDATION only",
                "No GridSearch / Optuna / deep learning",
            ],
        }
        (art_dir / "metrics.json").write_text(
            json.dumps(meta, indent=2, default=str), encoding="utf-8"
        )
        (art_dir / "feature_schema.json").write_text(
            json.dumps(
                {
                    "features": feat_names,
                    "target": target,
                    "schema": pipe.schema.model_dump() if pipe.schema else None,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return meta


def load_dataset_for_training(
    *,
    dataset_id: Optional[str] = None,
    dataset_dir: Optional[str] = None,
) -> LoadedDataset:
    """Resolve Phase 8 dataset from in-memory store or disk."""
    from app.ml.dataset_builder import get_dataset

    if dataset_dir:
        return DatasetLoader().load(dataset_dir, dataset_id=dataset_id)
    if not dataset_id:
        raise ValueError("dataset_id or dataset_dir required")
    stored = get_dataset(dataset_id)
    if stored is None:
        # try default disk location
        disk = Path("data/ml_datasets") / dataset_id
        if disk.exists():
            return DatasetLoader().load(disk, dataset_id=dataset_id)
        raise ValueError(f"Unknown dataset_id: {dataset_id}")
    return DatasetLoader().load(stored.output_dir, dataset_id=dataset_id)


def _infer_task(target: str, label_names: Sequence[str]) -> str:
    if target in REGRESSION_TARGETS or target.startswith("return_") or target == "future_R":
        return "regression"
    if target in CLASSIFICATION_TARGETS:
        return "classification"
    if target in label_names:
        if target.startswith("return") or target in ("future_R", "mfe_5", "mae_5"):
            return "regression"
        return "classification"
    raise ValueError(f"Unknown target: {target}")


def _eval(task: str, y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    if len(y_true) == 0:
        return {}
    if task == "regression":
        return regression_metrics(y_true.astype(float), y_pred.astype(float))
    return classification_metrics(y_true, y_pred)


def _trade_only_eval(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    mask = [str(y) in ("WIN", "LOSS") for y in y_true]
    yt = [str(y) for y, m in zip(y_true, mask) if m]
    yp = [str(y) for y, m in zip(y_pred, mask) if m]
    if not yt:
        return {"n": 0, "note": "No WIN/LOSS rows in split"}
    return classification_metrics(yt, yp)


def _selection_score(task: str, primary: Dict[str, Any], fallback: Dict[str, Any]) -> float:
    m = primary or fallback or {}
    if task == "regression":
        mae = m.get("mae")
        return float(-mae) if mae is not None else -999.0
    return float(m.get("f1_macro") or m.get("balanced_accuracy") or 0.0)


def _primary(task: str, m: Dict[str, Any]) -> float:
    if not m:
        return 0.0
    if task == "regression":
        return float(-(m.get("mae") or 0.0))
    return float(m.get("f1_macro") or 0.0)


def _class_counts(y: Sequence[Any]) -> Dict[str, Any]:
    from collections import Counter

    c = Counter(str(x) for x in y)
    total = sum(c.values()) or 1
    return {
        "counts": dict(c),
        "percentages": {k: round(v / total, 6) for k, v in c.items()},
    }


def _top_features(imp: Dict[str, float], n: int) -> List[Dict[str, Any]]:
    items = sorted(imp.items(), key=lambda x: abs(x[1]), reverse=True)[:n]
    return [{"feature": k, "importance": round(float(v), 6)} for k, v in items]


def _explainability(imp: Dict[str, float], model: Any) -> Dict[str, Any]:
    top = _top_features(imp, 15)
    out: Dict[str, Any] = {"top_features": top}
    # Logistic: signed coefficients for first class if available
    if getattr(model, "model_type", "") == "logistic" and model._model is not None:
        if hasattr(model._model, "coef_"):
            coef = np.asarray(model._model.coef_)
            names = model.feature_names_
            if coef.ndim == 1:
                pairs = list(zip(names, coef.tolist()))
            else:
                # multiclass: use first class coefficients for directionality
                pairs = list(zip(names, coef[0].tolist()))
            pairs_sorted = sorted(pairs, key=lambda x: x[1], reverse=True)
            out["top_positive"] = [
                {"feature": a, "coefficient": round(float(b), 6)} for a, b in pairs_sorted[:10]
            ]
            out["top_negative"] = [
                {"feature": a, "coefficient": round(float(b), 6)}
                for a, b in sorted(pairs, key=lambda x: x[1])[:10]
            ]
    return out


def _feature_from_ts(rows: Sequence[Dict[str, Any]], timestamp: str, key: str) -> Any:
    row = _find_row(rows, timestamp)
    return row.get(key) if row else None


def _find_row(rows: Sequence[Dict[str, Any]], timestamp: str) -> Optional[Dict[str, Any]]:
    for r in rows:
        if str(r.get("__timestamp")) == timestamp:
            return r
    return None
