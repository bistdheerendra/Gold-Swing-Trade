#!/usr/bin/env python3
"""
Binance PAXGUSDT candle-level ML — research sidecar.

Trains on data/historical/PAXGUSDT_*.csv only.
Writes artifacts/ml_candle_binance with model_id prefix binance_paxgusdt_*.
Does NOT touch Delta PAXGUSD datasets, Phase 6 thresholds, or combined GO path.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.backtest.data import parse_csv_ohlcv  # noqa: E402
from app.market.schemas import ANALYSIS_TIMEFRAMES  # noqa: E402
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

SYMBOL = "PAXGUSDT"
MODEL_PREFIX = "binance_paxgusdt_"


def _log(msg: str) -> None:
    print(msg, flush=True)


def load_binance_history() -> Dict[str, List]:
    hist = REPO_ROOT / "data" / "historical"
    bars_by_tf: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        path = hist / f"{SYMBOL}_{tf}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {path} — run scripts/backfill_binance_paxgusdt.py first"
            )
        bars = parse_csv_ohlcv(
            path, symbol=SYMBOL, timeframe=tf, source="binance_futures"
        )
        bars_by_tf[tf] = bars
        _log(f"  load {tf}: {len(bars)} bars")
    n15 = len(bars_by_tf["15m"])
    if n15 < 2000:
        raise RuntimeError(f"Expected substantial Binance 15m history, got {n15}")
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


def _prefix_model_artifacts(art_root: Path, train_out: Dict[str, Any]) -> str:
    """Rename artifact folder + registry model_id to binance_paxgusdt_*."""
    old_id = str(train_out.get("model_id") or "")
    if not old_id:
        raise RuntimeError("trainer returned no model_id")
    if old_id.startswith(MODEL_PREFIX):
        return old_id
    new_id = f"{MODEL_PREFIX}{old_id}"
    target = str(train_out.get("target") or "direction")
    old_dir = art_root / target / old_id
    new_dir = art_root / target / new_id
    if not old_dir.exists():
        raise FileNotFoundError(old_dir)
    if new_dir.exists():
        shutil.rmtree(new_dir)
    old_dir.rename(new_dir)
    for name in ("registry_entry.json", "metrics.json"):
        path = new_dir / name
        if not path.exists():
            continue
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta["model_id"] = new_id
        meta["artifact_dir"] = str(new_dir).replace("\\", "/")
        meta["research_track"] = "binance_paxgusdt"
        meta["source_symbol"] = SYMBOL
        meta["disclaimer"] = (
            "Binance PAXGUSDT research model — not Delta PAXGUSD; not Phase 12 GO"
        )
        path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    train_out["model_id"] = new_id
    return new_id


def main() -> int:
    _log("=== Binance PAXGUSDT candle ML (research sidecar) ===")
    _log(
        f"Constants: N={TRIPLE_BARRIER_HORIZON_BARS}, "
        f"k={TRIPLE_BARRIER_ATR_MULT}, atr={TRIPLE_BARRIER_ATR_PERIOD}"
    )

    out_root = REPO_ROOT / "data" / "ml_datasets_candle_binance"
    art_root = REPO_ROOT / "artifacts" / "ml_candle_binance"
    out_root.mkdir(parents=True, exist_ok=True)
    art_root.mkdir(parents=True, exist_ok=True)

    _log("=== Load Binance CSVs ===")
    bars_by_tf = load_binance_history()

    cfg = candle_level_dataset_config(
        symbol=SYMBOL,
        timeframe="15m",
        output_dir=str(out_root),
    )
    # Longer history than Delta — step keeps CPU near Phase 11.8 scale
    cfg.row_step = 3
    cfg.max_context_bars = 280

    _log("=== Build candle dataset ===")
    builder = DatasetBuilder(cfg)
    result = builder.build(
        bars_by_tf,
        source="binance_futures_csv",
        output_root=out_root,
        progress_every=500,
    )
    rows = get_dataset_rows(result.dataset_id) or []
    meta = result.metadata
    dist_all = class_dist(rows)
    _log(f"  dataset_id={result.dataset_id} rows={meta.row_count}")
    _log(f"  class_dist={dist_all}")

    _log("=== Train direction baselines ===")
    loaded = DatasetLoader().load(result.output_dir, dataset_id=result.dataset_id)
    trainer = ModelTrainer(
        artifacts_root=art_root,
        random_seed=42,
        model_version="binance_paxgusdt_1.0.0",
    )
    train_out = trainer.train(
        loaded,
        target="direction",
        model_types=["logistic", "random_forest"],
        run_test=True,
    )
    model_id = _prefix_model_artifacts(art_root, train_out)

    X_train, y_train, _ = extract_xy(loaded.train, loaded.feature_names, "direction")
    X_test, y_test, _ = extract_xy(loaded.test, loaded.feature_names, "direction")
    maj_pred = majority_predict(y_train, len(y_test))
    maj_metrics = classification_metrics(y_test, maj_pred)
    test_metrics = train_out.get("test_metrics") or {}
    test_acc = test_metrics.get("accuracy")
    maj_acc = maj_metrics.get("accuracy")
    skill = (
        float(test_acc) - float(maj_acc)
        if test_acc is not None and maj_acc is not None
        else None
    )

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "symbol": SYMBOL,
        "research_track": "binance_paxgusdt",
        "dataset_id": result.dataset_id,
        "row_count": meta.row_count,
        "source_bars_15m": len(bars_by_tf["15m"]),
        "class_distribution": dist_all,
        "model_id": model_id,
        "selected_model_type": train_out.get("selected_model_type"),
        "validation_metrics": train_out.get("validation_metrics"),
        "test_metrics": test_metrics,
        "majority_baseline_test": maj_metrics,
        "skill_vs_majority_acc": skill,
        "disclaimer": (
            "Research suggestion model only. Not Delta PAXGUSD. "
            "Not Phase 6/10 GO. Not Phase 12."
        ),
        "phase_6_10_untouched": True,
    }
    summary_path = REPO_ROOT / "docs" / "binance-paxgusdt-research.md"
    lines = [
        "# Binance PAXGUSDT Candle ML — Research Sidecar",
        "",
        f"**Generated:** {payload['generated_at']}",
        "",
        "> Separate from Delta PAXGUSD. Suggestions only — not Phase 12 GO.",
        "",
        f"- Symbol: `{SYMBOL}`",
        f"- dataset_id: `{result.dataset_id}`",
        f"- rows: **{meta.row_count}** (15m source bars: {len(bars_by_tf['15m'])})",
        f"- model_id: `{model_id}`",
        f"- selected: `{train_out.get('selected_model_type')}`",
        f"- test accuracy: `{test_acc}` vs majority `{maj_acc}` (Δ={skill})",
        "",
        "Set `BINANCE_ML_MODEL_ID` to this model_id for `/api/research/binance-suggest`.",
        "",
        "```json",
        json.dumps(payload, indent=2, default=str),
        "```",
        "",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")
    pointer = art_root / "SELECTED_MODEL_ID.txt"
    pointer.write_text(model_id + "\n", encoding="utf-8")
    _log(f"Wrote {summary_path}")
    _log(f"SELECTED model_id={model_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
