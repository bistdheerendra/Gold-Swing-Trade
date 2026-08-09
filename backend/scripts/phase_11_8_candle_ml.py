#!/usr/bin/env python3
"""
Phase 11.8 — build full-history candle-level ML dataset + retrain baselines.

Uses ALL available data/historical/PAXGUSD_*.csv bars (not UI bar_limit=220).
Does NOT wire into Phase 6/10. Does NOT overwrite Phase 8 datasets.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.backtest.data import parse_csv_ohlcv  # noqa: E402
from app.market.schemas import Timeframe  # noqa: E402
from app.ml.baselines import majority_predict  # noqa: E402
from app.ml.config import (  # noqa: E402
    TRIPLE_BARRIER_ATR_MULT,
    TRIPLE_BARRIER_ATR_PERIOD,
    TRIPLE_BARRIER_HORIZON_BARS,
    candle_level_dataset_config,
)
from app.ml.dataset_builder import DatasetBuilder, get_dataset_rows  # noqa: E402
from app.ml.dataset_loader import DatasetLoader, extract_xy  # noqa: E402
from app.ml.trainer import ModelTrainer  # noqa: E402
from app.ml.training_metrics import classification_metrics  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def load_full_history() -> Dict[str, List]:
    hist = REPO_ROOT / "data" / "historical"
    bars_by_tf: Dict[str, List] = {}
    for tf in Timeframe:
        path = hist / f"PAXGUSD_{tf.value}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path} — run Phase 11.5 backfill first")
        bars = parse_csv_ohlcv(path, symbol="PAXGUSD", timeframe=tf.value)
        bars_by_tf[tf.value] = bars
        _log(f"  load {tf.value}: {len(bars)} bars")
    n15 = len(bars_by_tf["15m"])
    if n15 < 1000:
        raise RuntimeError(
            f"Expected full Delta history (~16k 15m bars), got {n15}. "
            "Do not use UI bar_limit=220 for this phase."
        )
    return bars_by_tf


def class_dist(rows, key: str = "direction") -> Dict[str, Any]:
    c: Counter[str] = Counter()
    for r in rows:
        v = r.labels.get(key)
        if v is not None and v != "":
            c[str(v)] += 1
    total = sum(c.values()) or 1
    return {
        "counts": dict(c),
        "pct": {k: round(v / total, 4) for k, v in sorted(c.items())},
        "n": total,
    }


def main() -> int:
    _log("=== Phase 11.8: Candle-level ML labeling ===")
    _log(
        f"A priori constants: N={TRIPLE_BARRIER_HORIZON_BARS}, "
        f"k={TRIPLE_BARRIER_ATR_MULT}, atr_period={TRIPLE_BARRIER_ATR_PERIOD}"
    )
    _log("(Documented in docs/ml-labeling.md — will not retune on TEST)")

    out_root = REPO_ROOT / "data" / "ml_datasets_candle"
    art_root = REPO_ROOT / "artifacts" / "ml_candle"
    out_root.mkdir(parents=True, exist_ok=True)
    art_root.mkdir(parents=True, exist_ok=True)

    _log("=== Load full historical CSVs ===")
    bars_by_tf = load_full_history()

    cfg = candle_level_dataset_config(
        symbol="PAXGUSD",
        timeframe="15m",
        output_dir=str(out_root),
    )
    # Full candle density; keep tractable CPU with capped causal context
    cfg.row_step = 1
    cfg.max_context_bars = 280

    _log("=== Build candle-level dataset (full history, not bar_limit=220) ===")
    builder = DatasetBuilder(cfg)
    result = builder.build(
        bars_by_tf,
        source="delta_india_csv_full",
        output_root=out_root,
        progress_every=500,
    )
    rows = get_dataset_rows(result.dataset_id) or []
    meta = result.metadata
    dist_all = class_dist(rows)
    _log(f"  dataset_id={result.dataset_id}")
    _log(f"  rows={meta.row_count} start={meta.start} end={meta.end}")
    _log(f"  split={meta.split.model_dump() if hasattr(meta.split, 'model_dump') else meta.split}")
    _log(f"  class_dist={dist_all}")

    # Split date ranges from row timestamps
    n = len(rows)
    t_end = int(n * 0.70)
    v_end = int(n * 0.85)
    split_dates = {
        "train": {"start": rows[0].timestamp if rows else None, "end": rows[t_end - 1].timestamp if t_end else None, "n": t_end},
        "validation": {
            "start": rows[t_end].timestamp if t_end < n else None,
            "end": rows[v_end - 1].timestamp if v_end else None,
            "n": max(0, v_end - t_end),
        },
        "test": {
            "start": rows[v_end].timestamp if v_end < n else None,
            "end": rows[-1].timestamp if rows else None,
            "n": max(0, n - v_end),
        },
    }
    dist_train = class_dist(rows[:t_end])
    dist_val = class_dist(rows[t_end:v_end])
    dist_test = class_dist(rows[v_end:])

    _log("=== Train Phase 9 baselines on candle-level direction ===")
    loaded = DatasetLoader().load(result.output_dir, dataset_id=result.dataset_id)
    trainer = ModelTrainer(artifacts_root=art_root, random_seed=42, model_version="2.0.0-candle")
    train_out = trainer.train(
        loaded,
        target="direction",
        model_types=["logistic", "random_forest", "gradient_boosting"],
        run_test=True,
    )

    # Majority baseline on TEST
    X_train, y_train, _ = extract_xy(loaded.train, loaded.feature_names, "direction")
    X_test, y_test, _ = extract_xy(loaded.test, loaded.feature_names, "direction")
    maj_pred = majority_predict(y_train, len(y_test))
    maj_metrics = classification_metrics(y_test, maj_pred)

    selected = train_out.get("selected_model_type")
    test_metrics = train_out.get("test_metrics") or {}
    val_metrics = train_out.get("validation_metrics") or {}
    test_acc = (test_metrics or {}).get("accuracy")
    maj_acc = maj_metrics.get("accuracy")
    skill = None
    if test_acc is not None and maj_acc is not None:
        skill = float(test_acc) - float(maj_acc)

    # Honest verdict
    if skill is None:
        verdict = "INCONCLUSIVE"
        verdict_text = "Could not compare model accuracy to majority baseline."
    elif skill < 0.01 and float(test_metrics.get("balanced_accuracy") or 0) < (
        float(maj_metrics.get("balanced_accuracy") or 0) + 0.02
    ):
        verdict = "NO_REAL_SKILL"
        verdict_text = (
            f"No meaningful skill vs majority baseline "
            f"(test_acc={test_acc}, majority_acc={maj_acc}, Δ={skill:.4f}). "
            "FLAT dominance or weak features — research-only; do not wire to Phase 6/10."
        )
    else:
        verdict = "WEAK_OR_POSITIVE_SIGNAL"
        verdict_text = (
            f"Model beats majority baseline by Δacc={skill:.4f} "
            f"(test_acc={test_acc}, majority_acc={maj_acc}). "
            "Still research-only until a separate wiring decision; Phase 12 remains NO-GO "
            "until strategy expectancy gates are also cleared."
        )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "constants": {
            "N": TRIPLE_BARRIER_HORIZON_BARS,
            "k": TRIPLE_BARRIER_ATR_MULT,
            "atr_period": TRIPLE_BARRIER_ATR_PERIOD,
            "note": "Fixed a priori — not retuned on TEST",
        },
        "dataset_id": result.dataset_id,
        "output_dir": result.output_dir,
        "row_count": meta.row_count,
        "source_bars_15m": len(bars_by_tf["15m"]),
        "split_dates": split_dates,
        "class_distribution": {
            "all": dist_all,
            "train": dist_train,
            "validation": dist_val,
            "test": dist_test,
        },
        "selected_model_type": selected,
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "majority_baseline_test": maj_metrics,
        "skill_vs_majority_acc": skill,
        "train_summary": {
            "model_id": train_out.get("model_id"),
            "overfitting": train_out.get("overfitting"),
            "baselines": train_out.get("baselines"),
        },
        "verdict": verdict,
        "verdict_text": verdict_text,
        "phase_6_10_untouched": True,
    }

    # Calibration note from trainer if present
    if train_out.get("test_metrics"):
        payload["calibration_note"] = (
            "See model artifact test metrics / calibration buckets when available. "
            "Majority FLAT baseline can inflate accuracy — prefer balanced_accuracy + per-class recall."
        )

    results_path = REPO_ROOT / "docs" / "phase-11.8-candle-ml-results.md"
    lines = [
        "# Phase 11.8 — Candle-Level ML Results",
        "",
        f"**Generated:** {payload['generated_at']}",
        "",
        "## Constants (a priori)",
        "",
        f"- `N` (horizon bars) = **{TRIPLE_BARRIER_HORIZON_BARS}**",
        f"- `k` (ATR multiple) = **{TRIPLE_BARRIER_ATR_MULT}**",
        f"- ATR period = **{TRIPLE_BARRIER_ATR_PERIOD}**",
        "",
        "See [docs/ml-labeling.md](ml-labeling.md). Not retuned after TEST.",
        "",
        "## Dataset",
        "",
        f"- dataset_id: `{result.dataset_id}`",
        f"- rows: **{meta.row_count}** (source 15m bars: {len(bars_by_tf['15m'])})",
        f"- range: `{meta.start}` → `{meta.end}`",
        f"- output: `{result.output_dir}`",
        f"- Phase 8 path untouched: `data/ml_datasets/`",
        "",
        "### Split date ranges",
        "",
        "```json",
        json.dumps(split_dates, indent=2),
        "```",
        "",
        "### Class distribution (UP / DOWN / FLAT)",
        "",
        "```json",
        json.dumps(payload["class_distribution"], indent=2),
        "```",
        "",
        "## Model evaluation (held-out TEST once)",
        "",
        f"- Selected model: `{selected}`",
        "",
        "### Validation metrics",
        "",
        "```json",
        json.dumps(val_metrics, indent=2, default=str),
        "```",
        "",
        "### Test metrics",
        "",
        "```json",
        json.dumps(test_metrics, indent=2, default=str),
        "```",
        "",
        "### Majority-class baseline (TEST)",
        "",
        "```json",
        json.dumps(maj_metrics, indent=2, default=str),
        "```",
        "",
        f"**Skill vs majority (accuracy Δ):** `{skill}`",
        "",
        "## Verdict",
        "",
        f"**{verdict}**",
        "",
        verdict_text,
        "",
        "## Constraints honored",
        "",
        "- Full history used (not UI `bar_limit=220`)",
        "- Features causal; labels forward-looking by design",
        "- Chronological 70/15/15 split",
        "- Phase 6 / Phase 10 pipelines untouched",
        "- Phase 12 remains blocked pending strategy GO",
        "",
    ]
    results_path.write_text("\n".join(lines), encoding="utf-8")
    _log(f"Wrote {results_path}")

    summary_json = out_root / f"{result.dataset_id}_phase_11_8_summary.json"
    summary_json.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    _log(f"Wrote {summary_json}")
    _log(f"VERDICT: {verdict}")
    _log(verdict_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
