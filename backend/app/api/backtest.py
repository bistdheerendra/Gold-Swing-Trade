"""Backtest HTTP API (Phase 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.backtest.config import (
    AmbiguityPolicy,
    BacktestConfig,
    BacktestCostConfig,
    BacktestExecutionConfig,
    CostMode,
    RiskSizingMode,
    TpMode,
)
from app.backtest.data import CsvHistoricalAdapter, ProviderHistoricalAdapter
from app.backtest.engine import BacktestEngine, clear_results, get_result, store_result
from app.backtest.schemas import BacktestResult, BacktestRunRequest, BacktestTrade
from app.core.config import Settings, get_settings
from app.core.errors import ValidationAppError
from app.market.deps import get_market_service
from app.market.schemas import ANALYSIS_TIMEFRAMES, ensure_utc, parse_timeframe
from app.market.service import MarketDataService
from app.strategy.config import StrategyConfig

router = APIRouter(prefix="/backtest", tags=["backtest"])


class BacktestTradesResponse(BaseModel):
    backtest_id: str
    count: int
    trades: List[BacktestTrade]


@router.post("/run", response_model=BacktestResult)
async def run_backtest(
    body: BacktestRunRequest,
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BacktestResult:
    try:
        parse_timeframe(body.timeframe)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc

    start = _parse_dt(body.start) if body.start else None
    end = _parse_dt(body.end) if body.end else None
    if start and end and start >= end:
        raise ValidationAppError("start must be before end")

    cost = BacktestCostConfig()
    if body.cost_config:
        cost = BacktestCostConfig(
            mode=CostMode(body.cost_config.get("mode", CostMode.REALISTIC_COST.value)),
            spread_points=float(body.cost_config.get("spread_points", 0.30)),
            slippage_points=float(body.cost_config.get("slippage_points", 0.10)),
            commission_per_trade=float(body.cost_config.get("commission_per_trade", 0.0)),
        )
    execution = BacktestExecutionConfig()
    if body.execution_config:
        execution = BacktestExecutionConfig(
            ambiguity_policy=AmbiguityPolicy(
                body.execution_config.get("ambiguity_policy", AmbiguityPolicy.CONSERVATIVE.value)
            ),
            tp_mode=TpMode(body.execution_config.get("tp_mode", TpMode.FULL_AT_TP1.value)),
            max_signal_age_bars=body.execution_config.get("max_signal_age_bars"),
            allow_pyramiding=bool(body.execution_config.get("allow_pyramiding", False)),
        )

    try:
        risk_mode = RiskSizingMode((body.risk_mode or "FIXED_1R").upper())
    except ValueError as exc:
        raise ValidationAppError(
            "risk_mode must be FIXED_1R or RISK_PERCENT"
        ) from exc

    cfg = BacktestConfig(
        symbol=(body.symbol or settings.market_symbol).upper(),
        entry_timeframe=body.timeframe,
        initial_equity=body.initial_equity,
        risk_fraction_per_trade=body.risk_fraction_per_trade,
        risk_mode=risk_mode,
        cost=cost,
        execution=execution,
        strategy_version=(
            settings.strategy_version
            if settings.strategy_version not in ("", "none")
            else "1.0.0"
        ),
        warmup_bars=body.warmup_bars,
        signal_mode=body.signal_mode or "RULE_ONLY",
        model_id=body.model_id,
        min_ml_confidence=body.min_ml_confidence,
        step=max(1, getattr(body, "step", 1) or 1),
    )

    # Load multi-TF bars
    bars_by_tf: Dict[str, List] = {}
    if body.source == "csv":
        if not body.csv_path:
            raise ValidationAppError("csv_path required when source=csv")
        adapter = CsvHistoricalAdapter(body.csv_path)
        entry = await adapter.load(
            cfg.symbol, body.timeframe, start=start, end=end, limit=body.limit
        )
        bars_by_tf[body.timeframe] = entry
    else:
        adapter = ProviderHistoricalAdapter(service)
        for tf in ANALYSIS_TIMEFRAMES:
            bars_by_tf[tf] = await adapter.load(
                cfg.symbol, tf, start=start, end=end, limit=body.limit
            )

    engine = BacktestEngine(
        cfg,
        strategy_config=StrategyConfig(
            strategy_version=cfg.strategy_version,
            min_rr=settings.min_rr,
        ),
    )
    try:
        result = engine.run(
            bars_by_tf,
            start=start,
            end=end,
            split_segment=body.split_segment or "ALL",
        )
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc
    return store_result(result)


@router.get("/{backtest_id}", response_model=BacktestResult)
async def get_backtest(backtest_id: str) -> BacktestResult:
    result = get_result(backtest_id)
    if result is None:
        raise ValidationAppError(f"Unknown backtest_id: {backtest_id}")
    return result


@router.get("/{backtest_id}/trades", response_model=BacktestTradesResponse)
async def get_backtest_trades(backtest_id: str) -> BacktestTradesResponse:
    result = get_result(backtest_id)
    if result is None:
        raise ValidationAppError(f"Unknown backtest_id: {backtest_id}")
    return BacktestTradesResponse(
        backtest_id=backtest_id, count=len(result.trades), trades=result.trades
    )


@router.post("/clear")
async def clear_backtests() -> dict:
    clear_results()
    return {"status": "cleared"}


def _parse_dt(raw: str) -> datetime:
    try:
        return ensure_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except Exception as exc:  # noqa: BLE001
        raise ValidationAppError(f"Invalid datetime: {raw}") from exc
