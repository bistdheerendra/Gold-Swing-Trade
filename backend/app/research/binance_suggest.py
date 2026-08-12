"""Binance PAXGUSDT research suggestion — isolated from Delta Phase 6/10 GO."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.backtest.data import parse_csv_ohlcv
from app.combined.features import build_feature_row
from app.combined.model_runtime import (
    ModelUnavailableError,
    load_runtime_model,
    predict_ml,
)
from app.core.config import get_settings
from app.market.schemas import ANALYSIS_TIMEFRAMES, OHLCVBar
from app.ml.model_registry import register_model
from app.smc.engine import SmcEngine
from app.strategy.config import StrategyConfig
from app.strategy.signal_engine import compute_levels
from app.ta.engine import TechnicalAnalysisEngine

REPO_ROOT = Path(__file__).resolve().parents[3]


DISCLAIMER = (
    "Binance-trained · reference only. Separate from Delta PAXGUSD strategy. "
    "Not Phase 12 GO. Not broker advice."
)


def _artifacts_root() -> Path:
    settings = get_settings()
    root = Path(settings.binance_ml_artifacts_root)
    if not root.is_absolute():
        root = REPO_ROOT / root
    return root


def resolve_binance_model_id(explicit: Optional[str] = None) -> str:
    settings = get_settings()
    if explicit:
        return explicit.strip()
    if settings.binance_ml_model_id.strip():
        return settings.binance_ml_model_id.strip()
    pointer = _artifacts_root() / "SELECTED_MODEL_ID.txt"
    if pointer.exists():
        return pointer.read_text(encoding="utf-8").strip()
    root = _artifacts_root()
    if not root.exists():
        raise ModelUnavailableError(
            "No Binance research artifacts — run backfill + phase_binance_paxgusdt_candle_ml.py"
        )
    entries = sorted(root.rglob("registry_entry.json"), key=lambda p: p.stat().st_mtime)
    if not entries:
        raise ModelUnavailableError("No binance_paxgusdt registry entries found")
    meta = json.loads(entries[-1].read_text(encoding="utf-8"))
    mid = str(meta.get("model_id") or "")
    if not mid:
        raise ModelUnavailableError("registry_entry missing model_id")
    return mid


def _load_meta(model_id: str) -> Dict[str, Any]:
    root = _artifacts_root()
    for path in root.rglob("registry_entry.json"):
        meta = json.loads(path.read_text(encoding="utf-8"))
        if meta.get("model_id") == model_id:
            art = Path(meta.get("artifact_dir") or path.parent)
            if not art.is_absolute():
                art = REPO_ROOT / art
            meta["artifact_dir"] = str(art)
            return meta
    for path in root.rglob("metrics.json"):
        if path.parent.name == model_id:
            meta = json.loads(path.read_text(encoding="utf-8"))
            meta["model_id"] = model_id
            meta["artifact_dir"] = str(path.parent)
            return meta
    raise ModelUnavailableError(f"Unknown Binance research model_id: {model_id}")


def load_binance_bars_from_csv(*, limit: int = 400) -> Dict[str, List[OHLCVBar]]:
    hist = REPO_ROOT / "data" / "historical"
    symbol = get_settings().binance_paxgusdt_symbol
    out: Dict[str, List[OHLCVBar]] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        path = hist / f"{symbol}_{tf}.csv"
        if not path.exists():
            continue
        bars = parse_csv_ohlcv(
            path, symbol=symbol, timeframe=tf, source="binance_futures"
        )
        out[tf] = bars[-limit:] if limit else bars
    if "15m" not in out or not out["15m"]:
        raise FileNotFoundError(
            f"Missing {hist / (symbol + '_15m.csv')} — run backfill_binance_paxgusdt.py"
        )
    return out


def _train_window_meta(symbol: str) -> Dict[str, Any]:
    """Full CSV span used for training (not the suggest limit window)."""
    path = REPO_ROOT / "data" / "historical" / f"{symbol}_15m.csv"
    if not path.exists():
        return {"train_span_months": 16.5, "train_span_label": "16.5 mo train"}
    bars = parse_csv_ohlcv(path, symbol=symbol, timeframe="15m", source="binance_futures")
    if len(bars) < 2:
        return {"train_span_months": 16.5, "train_span_label": "16.5 mo train"}
    first = bars[0].timestamp
    last = bars[-1].timestamp
    if first.tzinfo is None:
        first = first.replace(tzinfo=timezone.utc)
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    days = max(0, (last - first).days)
    months = round(days / 30.44, 1)
    return {
        "train_span_days": days,
        "train_span_months": months,
        "train_span_label": f"{months} mo train",
        "train_from": first.isoformat(),
        "train_to": last.isoformat(),
        "train_bars_15m": len(bars),
    }


def _research_levels(
    *,
    bullish: bool,
    bars_by_tf: Dict[str, List[OHLCVBar]],
    symbol: str,
) -> Dict[str, Any]:
    """SMC/ATR geometry on Binance bars — research levels for the ML lean."""
    bars_15 = bars_by_tf["15m"]
    bars_1h = bars_by_tf.get("1h") or []
    smc_15 = SmcEngine().analyze(
        bars_15, symbol=symbol, timeframe="15m", as_of_index=len(bars_15) - 1
    )
    smc_1h = None
    if len(bars_1h) >= 40:
        smc_1h = SmcEngine().analyze(
            bars_1h, symbol=symbol, timeframe="1h", as_of_index=len(bars_1h) - 1
        )
    ta = TechnicalAnalysisEngine().analyze(
        bars_15, symbol=symbol, timeframe="15m", as_of_index=len(bars_15) - 1
    )
    atr = ta.latest.atr
    levels = compute_levels(
        bullish=bullish,
        bars_15m=bars_15,
        smc_1h=smc_1h,
        smc_15m=smc_15,
        atr=atr,
        config=StrategyConfig(strategy_version="1.0.0"),
    )
    entry = None
    if levels.entry is not None:
        entry = {
            "low": levels.entry.low,
            "high": levels.entry.high,
            "preferred": levels.entry.preferred,
        }
    targets = [
        {"price": t.price, "rr": t.rr, "label": t.label} for t in (levels.targets or [])
    ]
    return {
        "entry": entry,
        "stop_loss": levels.stop_loss,
        "targets": targets,
        "primary_rr": levels.primary_rr,
        "atr": atr,
        "level_errors": list(levels.errors or []),
        "level_warnings": list(levels.warnings or []),
    }


def suggest_from_binance(
    *,
    model_id: Optional[str] = None,
    limit: int = 400,
) -> Dict[str, Any]:
    settings = get_settings()
    if not settings.binance_suggest_enabled:
        return {
            "enabled": False,
            "disclaimer": DISCLAIMER,
            "error": "BINANCE_SUGGEST_ENABLED=false",
        }

    mid = resolve_binance_model_id(model_id)
    meta = _load_meta(mid)
    register_model(meta)
    runtime = load_runtime_model(mid)

    bars_by_tf = load_binance_bars_from_csv(limit=limit)
    entry_bars = bars_by_tf["15m"]
    as_of = entry_bars[-1].timestamp
    features, bar, _ = build_feature_row(bars_by_tf, as_of=as_of, entry_tf="15m")

    mapped, conf, detail = predict_ml(runtime, features, rule_direction="NEUTRAL")
    raw = str(detail.get("raw_prediction") or "").upper()
    if raw == "FLAT":
        mapped = "NEUTRAL"

    suggestion = "WAIT"
    signal = "WAIT"
    if mapped == "BUY":
        suggestion = "LEAN_LONG"
        signal = "BUY"
    elif mapped == "SELL":
        suggestion = "LEAN_SHORT"
        signal = "SHORT"

    levels: Optional[Dict[str, Any]] = None
    if mapped in ("BUY", "SELL"):
        try:
            levels = _research_levels(
                bullish=(mapped == "BUY"),
                bars_by_tf=bars_by_tf,
                symbol=settings.binance_paxgusdt_symbol,
            )
        except Exception as exc:  # noqa: BLE001
            levels = {
                "entry": None,
                "stop_loss": None,
                "targets": [],
                "primary_rr": None,
                "level_errors": [f"levels_failed: {exc}"],
                "level_warnings": [],
            }
        # No actionable near-spot plan → keep ML lean text, but do not show a trade
        if levels and (
            levels.get("entry") is None
            or levels.get("stop_loss") is None
            or not levels.get("targets")
            or levels.get("level_errors")
        ):
            signal = "WAIT"
            if not levels.get("level_errors"):
                levels["level_errors"] = [
                    "No actionable near-spot entry/SL/TP for this lean"
                ]

    train_meta = _train_window_meta(settings.binance_paxgusdt_symbol)

    return {
        "enabled": True,
        "as_of": ensure_iso(as_of),
        "symbol": settings.binance_paxgusdt_symbol,
        "source": "binance_futures",
        "model_id": runtime.model_id,
        "model_type": runtime.model_type,
        "target": runtime.target,
        "raw_prediction": detail.get("raw_prediction"),
        "mapped_direction": mapped,
        "signal": signal,
        "suggestion": suggestion,
        "confidence": round(float(conf), 4),
        "bar_close": bar.close,
        "entry": (levels or {}).get("entry"),
        "stop_loss": (levels or {}).get("stop_loss"),
        "targets": (levels or {}).get("targets") or [],
        "primary_rr": (levels or {}).get("primary_rr"),
        "atr": (levels or {}).get("atr"),
        "level_errors": (levels or {}).get("level_errors") or [],
        "train_span_months": train_meta.get("train_span_months"),
        "train_span_label": train_meta.get("train_span_label"),
        "train_from": train_meta.get("train_from"),
        "train_to": train_meta.get("train_to"),
        "disclaimer": DISCLAIMER,
        "phase12_status": "NO_GO",
        "affects_delta_strategy": False,
        "detail": {
            "classes": detail.get("classes"),
            "mapping": detail.get("mapping"),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def ensure_iso(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.isoformat()
