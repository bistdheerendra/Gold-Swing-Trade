"""Strategy / signal HTTP API (Phase 6)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Dict, List, Optional, Sequence

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.core.errors import ValidationAppError
from app.market.deps import get_market_service
from app.market.schemas import OHLCVBar, OHLCVQuery, Timeframe, ensure_utc, parse_timeframe
from app.market.service import MarketDataService
from app.mtf.analyzer import DEFAULT_TFS
from app.strategy.config import ScoreWeights, StrategyConfig
from app.strategy.engine import StrategyEngine, get_signal_store, reset_signal_store
from app.strategy.schemas import StrategyAnalyzeResult, StrategyHistoryResponse

router = APIRouter(prefix="/strategy", tags=["strategy"])


def _config_from_settings(
    settings: Settings,
    *,
    min_rr: Optional[float] = None,
    signal_threshold: Optional[float] = None,
    wait_threshold: Optional[float] = None,
    strong_signal_threshold: Optional[float] = None,
    max_signal_age_bars: Optional[int] = None,
    sl_buffer: Optional[float] = None,
) -> StrategyConfig:
    return StrategyConfig(
        strategy_version=settings.strategy_version
        if settings.strategy_version not in ("0.1.0", "none", "")
        else "1.0.0",
        min_rr=min_rr if min_rr is not None else settings.min_rr,
        signal_threshold=signal_threshold if signal_threshold is not None else 65,
        wait_threshold=wait_threshold if wait_threshold is not None else 50,
        strong_signal_threshold=(
            strong_signal_threshold if strong_signal_threshold is not None else 80
        ),
        max_signal_age_bars=max_signal_age_bars if max_signal_age_bars is not None else 12,
        sl_buffer=sl_buffer if sl_buffer is not None else 0.5,
        score_weights=ScoreWeights(),
    )


@router.get("/analyze", response_model=StrategyAnalyzeResult)
async def analyze_strategy(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    symbol: Optional[str] = Query(default=None),
    as_of: Optional[datetime] = Query(
        default=None,
        description="UTC analysis time. Only CLOSED candles are used.",
    ),
    timeframes: Optional[str] = Query(
        default="1d,4h,1h,30m,15m",
        description="Comma-separated timeframes",
    ),
    limit: int = Query(default=500, ge=50, le=50_000),
    min_rr: Optional[float] = Query(default=None, ge=0.1),
    signal_threshold: Optional[float] = Query(default=None, ge=0, le=100),
    wait_threshold: Optional[float] = Query(default=None, ge=0, le=100),
    strong_signal_threshold: Optional[float] = Query(default=None, ge=0, le=100),
    max_signal_age_bars: Optional[int] = Query(default=None, ge=1, le=500),
    sl_buffer: Optional[float] = Query(default=None, ge=0),
) -> StrategyAnalyzeResult:
    sym = (symbol or settings.market_symbol).upper()
    tf_list = _parse_tf_list(timeframes)
    as_of_utc = ensure_utc(as_of or datetime.now(timezone.utc))

    bars_by_tf: Dict[str, List[OHLCVBar]] = {}
    for tf in tf_list:
        bars = await service.get_ohlcv(
            OHLCVQuery(symbol=sym, timeframe=tf, limit=limit)
        )
        if not bars:
            bars, _ = await service.ensure_sample_data(sym, tf, bars=max(limit, 300))
        bars_by_tf[tf.value] = list(bars)

    config = _config_from_settings(
        settings,
        min_rr=min_rr,
        signal_threshold=signal_threshold,
        wait_threshold=wait_threshold,
        strong_signal_threshold=strong_signal_threshold,
        max_signal_age_bars=max_signal_age_bars,
        sl_buffer=sl_buffer,
    )
    engine = StrategyEngine(config=config, store=get_signal_store())
    try:
        return engine.analyze(
            bars_by_tf,
            symbol=sym,
            as_of=as_of_utc,
            timeframes=[tf.value for tf in tf_list],
        )
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc


@router.get("/history", response_model=StrategyHistoryResponse)
async def strategy_history(
    settings: Annotated[Settings, Depends(get_settings)],
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> StrategyHistoryResponse:
    sym = (symbol or settings.market_symbol).upper()
    store = get_signal_store()
    # Only return stored BUY/SELL (and any persisted) — filter NO_TRADE spam
    signals = [
        s
        for s in store.history(symbol=sym, limit=limit * 3)
        if s.direction.value in ("BUY", "SELL", "WAIT")
    ][:limit]
    return StrategyHistoryResponse(symbol=sym, count=len(signals), signals=signals)


@router.post("/history/clear")
async def clear_strategy_history() -> dict:
    """Dev/test helper — clears in-memory signal history."""
    reset_signal_store()
    return {"status": "cleared"}


def _parse_tf_list(raw: Optional[str]) -> Sequence[Timeframe]:
    if not raw:
        return [parse_timeframe(x) for x in DEFAULT_TFS]
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        raise ValidationAppError("timeframes must not be empty")
    try:
        return [parse_timeframe(p) for p in parts]
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc
