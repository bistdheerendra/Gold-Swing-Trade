#!/usr/bin/env python3
"""
Phase 11.5 — re-validate Phases 7–11 on real market data.

Order:
  1) Load real OHLCV CSVs (Delta India PAXGUSD backfill)
  2) Phase 7 rule backtest
  3) Phase 8 ML dataset rebuild
  4) Phase 9 retrain baselines (discard prior synthetic artifacts first)
  5) Phase 10 RULE_ONLY vs ML_FILTER compare
  6) Phase 11 risk sizing sanity on real ATR/price

Writes docs/phase-11.5-real-data-validation.md with honest metrics.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.backtest.config import (  # noqa: E402
    AmbiguityPolicy,
    BacktestConfig,
    BacktestCostConfig,
    BacktestExecutionConfig,
    CostMode,
)
from app.backtest.data import parse_csv_ohlcv  # noqa: E402
from app.backtest.engine import BacktestEngine  # noqa: E402
from app.combined.threshold import DEFAULT_THRESHOLDS, select_threshold_on_validation  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.market.deps import get_memory_repository, get_provider, reset_market_singletons  # noqa: E402
from app.market.schemas import ANALYSIS_TIMEFRAMES, Timeframe  # noqa: E402
from app.market.service import MarketDataService  # noqa: E402
from app.market.validator import OHLCVValidator  # noqa: E402
from app.ml.config import DatasetConfig, FeatureConfig, LabelConfig  # noqa: E402
from app.ml.dataset_builder import DatasetBuilder  # noqa: E402
from app.ml.model_registry import clear_registry, register_model  # noqa: E402
from app.ml.trainer import ModelTrainer, load_dataset_for_training  # noqa: E402
from app.risk.config import AccountRiskConfig  # noqa: E402
from app.risk.engine import RiskEngine  # noqa: E402
from app.strategy.config import StrategyConfig  # noqa: E402
from app.strategy.schemas import SignalDirection, TakeProfitLevel  # noqa: E402
from app.ta.indicators import atr as compute_atr  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)

SYNTHETIC_BASELINE = {
    "note": (
        "Prior Phase 7–9 numbers were measured on mock/synthetic OHLCV "
        "(and/or small fixture windows). They are NOT a fair benchmark for "
        "live expectancy — listed only to show the migration delta."
    ),
    "phase7_mock_reference": {
        "source": "synthetic mock provider / early research runs",
        "win_rate": "n/a (not frozen as production truth)",
        "expectancy_r": "n/a",
        "max_drawdown_pct": "n/a",
        "comment": "Synthetic series overfit-friendly; real-data results replace them.",
    },
}


def _discard_synthetic_artifacts() -> List[str]:
    removed: List[str] = []
    art_root = BACKEND_ROOT / "artifacts" / "ml"
    if art_root.exists():
        for child in list(art_root.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
                removed.append(str(child.relative_to(BACKEND_ROOT)))
            elif child.is_file():
                child.unlink()
                removed.append(str(child.relative_to(BACKEND_ROOT)))
        art_root.mkdir(parents=True, exist_ok=True)
    clear_registry()
    return removed


async def _service() -> MarketDataService:
    reset_market_singletons()
    get_settings.cache_clear()
    return MarketDataService(
        provider=get_provider(),
        repository=get_memory_repository(),
        validator=OHLCVValidator(),
    )


async def load_real_bars(service: MarketDataService, symbol: str) -> Dict[str, int]:
    """Load Phase 11.5 CSV snapshots into the repository (no live re-fetch)."""
    hist = REPO_ROOT / "data" / "historical"
    counts: Dict[str, int] = {}
    for tf in Timeframe:
        path = hist / f"{symbol}_{tf.value}.csv"
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {path}. Run scripts/backfill_market_data.py first."
            )
        bars = parse_csv_ohlcv(
            path, symbol=symbol, timeframe=tf.value, source="real_delta_india"
        )
        # Cap interactive validation size while keeping ML/MTF lookback
        caps = {"15m": 1200, "30m": 900, "1h": 600, "4h": 300, "1d": 200}
        bars = bars[-caps.get(tf.value, 500) :]
        await service.repository.upsert_bars(bars)
        counts[tf.value] = len(bars)
        _log(f"  loaded {symbol} {tf.value}: {len(bars)} bars from {path.name}")
    return counts


def _metrics_summary(result) -> Dict[str, Any]:
    m = result.metrics
    return {
        "trades_entered": m.trades_entered,
        "win_rate": m.win_rate,
        "expectancy_r": m.expectancy_r,
        "profit_factor": m.profit_factor,
        "max_drawdown_pct": m.max_drawdown_pct,
        "net_profit_r": m.net_profit_r,
        "average_r": m.average_r,
        "final_equity": m.final_equity,
    }


async def phase7_backtest(service: MarketDataService, symbol: str) -> Dict[str, Any]:
    bars_by_tf: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        bars_by_tf[tf] = await service.repository.get_bars(
            symbol, Timeframe(tf), limit=1200
        )
    cfg = BacktestConfig(
        symbol=symbol,
        entry_timeframe="15m",
        warmup_bars=80,
        initial_equity=30_000.0,
        risk_fraction_per_trade=0.01,
        cost=BacktestCostConfig(mode=CostMode.REALISTIC_COST),
        execution=BacktestExecutionConfig(
            ambiguity_policy=AmbiguityPolicy.CONSERVATIVE
        ),
        strategy_version="1.0.0",
        signal_mode="RULE_ONLY",
        step=6,
    )
    engine = BacktestEngine(cfg, strategy_config=StrategyConfig(strategy_version="1.0.0"))
    result = engine.run(bars_by_tf, split_segment="ALL")
    return {
        "backtest_id": result.backtest_id,
        "bars_used": {k: len(v) for k, v in bars_by_tf.items()},
        "metrics": _metrics_summary(result),
        "notes": [
            "RULE_ONLY on real Delta India PAXGUSD candles",
            "Costs/slippage included (REALISTIC_COST)",
            "Results expected to differ from synthetic — reported honestly",
        ],
    }


async def phase8_9(
    service: MarketDataService, symbol: str
) -> tuple[Dict[str, Any], Dict[str, Any], Optional[str]]:
    bars_by_tf: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        bars_by_tf[tf] = await service.repository.get_bars(
            symbol, Timeframe(tf), limit=900
        )
    cfg = DatasetConfig(
        dataset_version="1.0.0-real-delta",
        symbol=symbol,
        timeframe="15m",
        warmup_bars=80,
        row_step=3,
        strategy_version="1.0.0",
        feature=FeatureConfig(feature_version="1.0.0", include_strategy=True),
        label=LabelConfig(label_version="1.0.0", include_strategy_outcome=True),
        output_dir=str(BACKEND_ROOT / "data" / "ml_datasets"),
    )
    builder = DatasetBuilder(cfg)
    dataset = builder.build(bars_by_tf, source="real_delta_india")
    meta = dataset.metadata
    ds_info = {
        "dataset_id": dataset.dataset_id,
        "rows": meta.row_count,
        "train": meta.split.train,
        "validation": meta.split.validation,
        "test": meta.split.test,
        "feature_version": meta.feature_version,
        "label_version": meta.label_version,
        "chronological_splits": True,
        "source": meta.source,
    }

    packed = load_dataset_for_training(dataset_id=dataset.dataset_id)
    trainer = ModelTrainer(
        artifacts_root=BACKEND_ROOT / "artifacts" / "ml",
        random_seed=42,
    )
    # Train all baselines; selection still validation-first
    train_result = trainer.train(
        packed,
        target="direction",
        model_type=None,
        run_test=True,
    )
    register_model(train_result)
    model_id = train_result.get("model_id")
    ml_info = {
        "model_id": model_id,
        "selected_model_type": train_result.get("selected_model_type"),
        "train_metrics": train_result.get("train_metrics"),
        "validation_metrics": train_result.get("validation_metrics"),
        "test_metrics": train_result.get("test_metrics"),
        "scores": train_result.get("scores"),
        "notes": train_result.get("notes")
        or ["Retrained on real OHLCV; synthetic artifacts discarded"],
    }
    return ds_info, ml_info, model_id


async def phase10_compare(
    service: MarketDataService, symbol: str, model_id: Optional[str]
) -> Dict[str, Any]:
    bars_by_tf: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        bars_by_tf[tf] = await service.repository.get_bars(
            symbol, Timeframe(tf), limit=900
        )
    base = dict(
        symbol=symbol,
        entry_timeframe="15m",
        warmup_bars=80,
        cost=BacktestCostConfig(mode=CostMode.ZERO_COST),
        execution=BacktestExecutionConfig(
            ambiguity_policy=AmbiguityPolicy.CONSERVATIVE
        ),
        strategy_version="1.0.0",
        model_id=model_id,
        step=8,
    )
    strat = StrategyConfig(strategy_version="1.0.0")
    selected_threshold = 0.60
    if model_id:
        runs = []
        for thr in DEFAULT_THRESHOLDS:
            rule_v = BacktestEngine(
                BacktestConfig(**base, signal_mode="RULE_ONLY"),
                strategy_config=strat,
            ).run(bars_by_tf, split_segment="VALIDATION")
            ml_v = BacktestEngine(
                BacktestConfig(
                    **base, signal_mode="ML_FILTER", min_ml_confidence=thr
                ),
                strategy_config=strat,
            ).run(bars_by_tf, split_segment="VALIDATION")
            runs.append({"threshold": thr, "rule_result": rule_v, "ml_result": ml_v})
        scan_info = select_threshold_on_validation(runs)
        selected_threshold = float(scan_info["selected_threshold"])

    rule_t = BacktestEngine(
        BacktestConfig(**base, signal_mode="RULE_ONLY"),
        strategy_config=strat,
    ).run(bars_by_tf, split_segment="TEST")
    out: Dict[str, Any] = {
        "threshold": selected_threshold,
        "rule_only_test": _metrics_summary(rule_t),
    }
    if model_id:
        ml_t = BacktestEngine(
            BacktestConfig(
                **base,
                signal_mode="ML_FILTER",
                min_ml_confidence=selected_threshold,
            ),
            strategy_config=strat,
        ).run(bars_by_tf, split_segment="TEST")
        out["ml_filter_test"] = _metrics_summary(ml_t)
        out["comparison_note"] = (
            "Do not assume ML improves expectancy. Both sides reported."
        )
    else:
        out["ml_filter_test"] = None
        out["comparison_note"] = "No model_id — skipped ML_FILTER leg"
    return out


async def phase11_risk(service: MarketDataService, symbol: str) -> Dict[str, Any]:
    bars = await service.repository.get_bars(symbol, Timeframe.H1, limit=200)
    if len(bars) < 30:
        return {"ok": False, "error": f"Insufficient bars for risk check: {len(bars)}"}

    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    atr_series = compute_atr(highs, lows, closes, period=14)
    atr_val = next((x for x in reversed(atr_series) if x is not None), None)
    last = bars[-1]
    price = last.close
    if atr_val is None or atr_val <= 0:
        return {"ok": False, "error": "ATR unavailable on real series"}

    entry = price
    stop = entry - 1.5 * atr_val
    tp_price = entry + 2.5 * atr_val
    rr = abs(tp_price - entry) / abs(entry - stop) if abs(entry - stop) > 0 else 0.0
    acct = AccountRiskConfig(account_balance=30_000.0, risk_per_trade_pct=1.0)
    engine = RiskEngine(account=acct)
    plan = engine.build_plan(
        symbol=symbol,
        direction=SignalDirection.BUY,
        entry=entry,
        stop_loss=stop,
        targets=[TakeProfitLevel(price=tp_price, rr=rr, label="TP1")],
        account=acct,
        rule_score=70,
        signal_notes=["Phase 11.5 real-data risk sanity"],
    )

    return {
        "ok": True,
        "symbol": symbol,
        "last_price": price,
        "atr_14_1h": atr_val,
        "atr_pct": (atr_val / price) * 100.0 if price else None,
        "price_source": last.source,
        "trade_plan": {
            "risk_status": plan.risk_status.value if plan.risk_status else None,
            "quantity": plan.quantity,
            "risk_amount": plan.risk_amount,
            "risk_amount_usd": plan.risk_amount_usd,
            "entry": plan.entry,
            "stop_loss": plan.stop_loss,
            "notional_value": plan.notional_value,
            "reasons": list(plan.reasons or [])[:5],
            "risks": list(plan.risks or [])[:5],
        },
        "notes": [
            "ATR and price levels from real candles (not synthetic ~2300 mock)",
            "Position size must track real stop distance / volatility",
        ],
    }


def _write_report(payload: Dict[str, Any]) -> Path:
    path = REPO_ROOT / "docs" / "phase-11.5-real-data-validation.md"
    sections = [
        ("Backfill", payload.get("backfill", {})),
        ("Discarded synthetic artifacts", payload.get("discarded_artifacts", [])),
        ("Synthetic baseline (reference only)", SYNTHETIC_BASELINE),
        ("Phase 7 — Rule backtest (real data)", payload.get("phase7", {})),
        ("Phase 8 — ML dataset (real data)", payload.get("phase8", {})),
        ("Phase 9 — ML training (real data)", payload.get("phase9", {})),
        ("Phase 10 — RULE_ONLY vs ML_FILTER", payload.get("phase10", {})),
        ("Phase 11 — Risk engine sanity", payload.get("phase11", {})),
    ]
    lines = [
        "# Phase 11.5 — Real Market Data Validation Report",
        "",
        f"**Generated:** {payload.get('generated_at')}",
        f"**Provider:** `{payload.get('provider')}`",
        f"**Symbol:** `{payload.get('symbol')}`",
        "",
        "> Honest research report. Real-data metrics replace synthetic ones. "
        "Worse live metrics are expected and not hidden.",
        "",
    ]
    for title, data in sections:
        lines.extend(
            [
                f"## {title}",
                "",
                "```json",
                json.dumps(data, indent=2, default=str),
                "```",
                "",
            ]
        )
    lines.extend(["## Verdict", "", payload.get("verdict", ""), ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


async def main_async() -> int:
    settings = get_settings()
    if settings.market_data_provider.lower().strip() == "mock":
        print(
            "ERROR: Set MARKET_DATA_PROVIDER=delta_india before validation.",
            file=sys.stderr,
        )
        return 2

    symbol = "PAXGUSD"
    discarded = _discard_synthetic_artifacts()
    _log(f"Discarded synthetic ML artifacts: {discarded or '(none)'}")

    service = await _service()
    _log("Loading real OHLCV from data/historical CSVs…")
    counts = await load_real_bars(service, symbol)
    _log(f"  bars: {counts}")

    _log("Phase 7 backtest…")
    p7 = await phase7_backtest(service, symbol)
    _log(f"  metrics: {p7.get('metrics')}")

    _log("Phase 8–9 dataset + train…")
    try:
        p8, p9, model_id = await phase8_9(service, symbol)
        _log(f"  dataset rows={p8.get('rows')} model={model_id}")
    except Exception as exc:  # noqa: BLE001
        _log(f"  ML pipeline error (reported honestly): {exc}")
        p8, p9, model_id = {"error": str(exc)}, {"error": str(exc)}, None

    _log("Phase 10 compare…")
    try:
        p10 = await phase10_compare(service, symbol, model_id)
        _log(f"  rule={p10.get('rule_only_test')} ml={p10.get('ml_filter_test')}")
    except Exception as exc:  # noqa: BLE001
        p10 = {"error": str(exc)}
        _log(f"  compare error: {exc}")

    _log("Phase 11 risk sanity…")
    p11 = await phase11_risk(service, symbol)
    _log(f"  price={p11.get('last_price')} atr={p11.get('atr_14_1h')}")

    verdict = (
        "Phase 11.5 validation completed on real Delta India PAXGUSD candles "
        "(symbol verified via /v2/products). Synthetic-trained model artifacts were discarded. "
        "Ready for Phase 12 only if backfill + Phase 7–11 sections above are green "
        "and PROJECT.md checklist is updated."
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": settings.market_data_provider,
        "symbol": symbol,
        "backfill": counts,
        "discarded_artifacts": discarded,
        "phase7": p7,
        "phase8": p8,
        "phase9": p9,
        "phase10": p10,
        "phase11": p11,
        "verdict": verdict,
    }
    path = _write_report(payload)
    _log(f"Wrote {path}")
    return 0 if p11.get("ok") else 1


def main() -> None:
    raise SystemExit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
