"""Combined Rule + ML signal API (Phase 10) — research only, no orders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.backtest.config import (
    AmbiguityPolicy,
    BacktestConfig,
    BacktestCostConfig,
    BacktestExecutionConfig,
    CostMode,
    TpMode,
)
from app.backtest.data import ProviderHistoricalAdapter
from app.backtest.engine import BacktestEngine, store_result
from app.combined.comparison import comparison_report
from app.combined.config import CombinedSignalConfig, MlFallbackMode
from app.combined.engine import CombinedSignalEngine
from app.combined.history import get_combined_store, reset_combined_store
from app.combined.schemas import CombinedSignalResult
from app.combined.threshold import DEFAULT_THRESHOLDS, select_threshold_on_validation
from app.core.config import Settings, get_settings
from app.core.errors import AppError, ValidationAppError
from app.market.deps import get_market_service
from app.market.schemas import ANALYSIS_TIMEFRAMES, OHLCVQuery, ensure_utc, parse_timeframe
from app.market.service import MarketDataService
from app.strategy.config import StrategyConfig

router = APIRouter(prefix="/combined", tags=["combined-signal"])


class CompareRequest(BaseModel):
    symbol: str = "XAUUSD"
    timeframe: str = "15m"
    model_id: Optional[str] = None
    # Keep enough history so TEST (~15%) still clears validation min_bars.
    limit: int = Field(default=400, ge=120, le=5000)
    warmup_bars: int = 80
    # If set, freeze this threshold (must come from validation research)
    min_ml_confidence: Optional[float] = None
    run_threshold_scan: bool = True
    evaluate_test: bool = True


@router.get("/analyze", response_model=CombinedSignalResult)
async def combined_analyze(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    symbol: Optional[str] = Query(default=None),
    as_of: Optional[datetime] = Query(default=None),
    model_id: Optional[str] = Query(default=None),
    mode: str = Query(default="ML_FILTER"),
    min_ml_confidence: Optional[float] = Query(default=None, ge=0, le=1),
    limit: int = Query(default=500, ge=50, le=50_000),
    ml_fallback: str = Query(default="FALLBACK_RULE"),
) -> CombinedSignalResult:
    sym = (symbol or settings.market_symbol).upper()
    as_of_utc = ensure_utc(as_of or datetime.now(timezone.utc))
    bars_by_tf: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        bars = await service.get_ohlcv(
            OHLCVQuery(symbol=sym, timeframe=parse_timeframe(tf), limit=limit)
        )
        if not bars:
            bars, _ = await service.ensure_sample_data(sym, tf, bars=max(limit, 300))
        bars_by_tf[tf] = list(bars)

    cfg = CombinedSignalConfig(
        model_id=model_id,
        min_ml_confidence=min_ml_confidence if min_ml_confidence is not None else 0.60,
        ml_fallback=MlFallbackMode(ml_fallback),
    )
    engine = CombinedSignalEngine(
        config=cfg,
        strategy_config=StrategyConfig(
            strategy_version=settings.strategy_version
            if settings.strategy_version not in ("", "none")
            else "1.0.0"
        ),
    )
    try:
        return engine.analyze(
            bars_by_tf,
            symbol=sym,
            as_of=as_of_utc,
            model_id=model_id,
            mode=mode.upper(),
        )
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc


@router.get("/history")
async def combined_history(
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    items = get_combined_store().list(symbol=symbol, limit=limit)
    return {
        "count": len(items),
        "signals": [i.model_dump(mode="json") for i in items],
        "label": "RESEARCH ONLY",
    }


@router.post("/history/clear")
async def clear_combined_history() -> dict:
    reset_combined_store()
    return {"status": "cleared"}


@router.post("/compare")
async def compare_rule_vs_ml(
    body: CompareRequest,
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    """
    Run RULE_ONLY and ML_FILTER on the same data.
    Threshold scan uses VALIDATION only; TEST evaluated once with frozen threshold.
    """
    try:
        parse_timeframe(body.timeframe)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc

    try:
        return await _run_rule_vs_ml_compare(body, service, settings)
    except AppError:
        raise
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc
    except Exception as exc:
        raise AppError(
            f"Compare failed: {type(exc).__name__}: {exc}",
            code="compare_failed",
            status_code=500,
        ) from exc


async def _run_rule_vs_ml_compare(
    body: CompareRequest,
    service: MarketDataService,
    settings: Settings,
) -> dict:
    adapter = ProviderHistoricalAdapter(service)
    bars_by_tf: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        bars_by_tf[tf] = await adapter.load(
            body.symbol.upper(), tf, limit=body.limit
        )

    base_cfg = dict(
        symbol=body.symbol.upper(),
        entry_timeframe=body.timeframe,
        warmup_bars=body.warmup_bars,
        cost=BacktestCostConfig(mode=CostMode.ZERO_COST),
        execution=BacktestExecutionConfig(ambiguity_policy=AmbiguityPolicy.CONSERVATIVE),
        strategy_version=settings.strategy_version
        if settings.strategy_version not in ("", "none")
        else "1.0.0",
        model_id=body.model_id,
        step=4,  # research compare speed; full step=1 for production research runs
    )
    strat = StrategyConfig(strategy_version=base_cfg["strategy_version"])

    # Validation threshold scan (optional)
    selected_threshold = (
        body.min_ml_confidence if body.min_ml_confidence is not None else 0.60
    )
    scan_info: dict = {"selected_threshold": selected_threshold, "scan": []}
    if body.run_threshold_scan and body.min_ml_confidence is None:
        runs = []
        for thr in DEFAULT_THRESHOLDS:
            rule_v = BacktestEngine(
                BacktestConfig(**base_cfg, signal_mode="RULE_ONLY"),
                strategy_config=strat,
            ).run(bars_by_tf, split_segment="VALIDATION")
            ml_v = BacktestEngine(
                BacktestConfig(
                    **base_cfg, signal_mode="ML_FILTER", min_ml_confidence=thr
                ),
                strategy_config=strat,
            ).run(bars_by_tf, split_segment="VALIDATION")
            store_result(rule_v)
            store_result(ml_v)
            runs.append({"threshold": thr, "rule_result": rule_v, "ml_result": ml_v})
        scan_info = select_threshold_on_validation(runs)
        selected_threshold = float(scan_info["selected_threshold"])

    # Frozen TEST (or ALL if evaluate_test false)
    split = "TEST" if body.evaluate_test else "ALL"
    rule_t = BacktestEngine(
        BacktestConfig(**base_cfg, signal_mode="RULE_ONLY"),
        strategy_config=strat,
    ).run(bars_by_tf, split_segment=split)
    ml_t = BacktestEngine(
        BacktestConfig(
            **base_cfg,
            signal_mode="ML_FILTER",
            min_ml_confidence=selected_threshold,
        ),
        strategy_config=strat,
    ).run(bars_by_tf, split_segment=split)
    store_result(rule_t)
    store_result(ml_t)

    report = comparison_report(
        rule_t,
        ml_t,
        threshold=selected_threshold,
        model_id=body.model_id,
        split=split,
    )
    report["validation_threshold_scan"] = scan_info
    report["rule_backtest_id"] = rule_t.backtest_id
    report["ml_backtest_id"] = ml_t.backtest_id
    return report
