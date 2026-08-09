"""SMC HTTP API (Phase 4)."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationAppError
from app.market.deps import get_market_service
from app.market.schemas import OHLCVQuery, parse_timeframe
from app.market.service import MarketDataService
from app.smc.engine import SmcEngine
from app.smc.schemas import SmcAnalysisResult, SmcConfig

router = APIRouter(prefix="/smc", tags=["smc"])


def _tf(value: str):
    try:
        return parse_timeframe(value)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc


@router.get("/analyze", response_model=SmcAnalysisResult)
async def analyze_smc(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    timeframe: str = Query(default="1h"),
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=30, le=50_000),
    as_of_index: Optional[int] = Query(default=None, ge=0),
    swing_left: int = Query(default=2, ge=1, le=10),
    swing_right: int = Query(default=2, ge=1, le=10),
    break_on_close: bool = Query(default=True),
    break_on_wick: bool = Query(default=False),
    liq_cluster_tolerance: float = Query(default=0.15, ge=0.0),
    liq_min_touches: int = Query(default=2, ge=1, le=20),
) -> SmcAnalysisResult:
    tf = _tf(timeframe)
    sym = (symbol or settings.market_symbol).upper()
    bars = await service.get_ohlcv(OHLCVQuery(symbol=sym, timeframe=tf, limit=limit))
    if not bars:
        bars, _ = await service.ensure_sample_data(sym, tf, bars=max(limit, 300))
    if not bars:
        raise NotFoundError(f"No OHLCV available for {sym} {tf.value}")
    if len(bars) < 10:
        raise ValidationAppError("Insufficient candles for SMC analysis (need >= 10)")

    config = SmcConfig(
        swing_left=swing_left,
        swing_right=swing_right,
        break_on_close=break_on_close,
        break_on_wick=break_on_wick,
        liq_cluster_tolerance=liq_cluster_tolerance,
        liq_min_touches=liq_min_touches,
    )
    engine = SmcEngine(config)
    try:
        return engine.analyze(
            bars, symbol=sym, timeframe=tf.value, as_of_index=as_of_index
        )
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc
