"""Technical analysis HTTP API (Phase 3)."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError, ValidationAppError
from app.market.deps import get_market_service
from app.market.schemas import OHLCVQuery, parse_timeframe
from app.market.service import MarketDataService
from app.ta.engine import TechnicalAnalysisEngine
from app.ta.schemas import TechnicalAnalysisConfig, TechnicalAnalysisResult

router = APIRouter(prefix="/ta", tags=["technical-analysis"])


def _tf(value: str):
    try:
        return parse_timeframe(value)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc


@router.get("/analyze", response_model=TechnicalAnalysisResult)
async def analyze(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    timeframe: str = Query(default="1h"),
    symbol: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=50, le=50_000),
    as_of_index: Optional[int] = Query(default=None, ge=0),
    swing_left: int = Query(default=2, ge=1, le=10),
    swing_right: int = Query(default=2, ge=1, le=10),
) -> TechnicalAnalysisResult:
    """
    Run the causal TA engine on stored OHLCV.

    If no bars exist, seeds mock data once (dev convenience — same as chart).
    """
    tf = _tf(timeframe)
    sym = (symbol or settings.market_symbol).upper()
    bars = await service.get_ohlcv(
        OHLCVQuery(symbol=sym, timeframe=tf, limit=limit)
    )
    if not bars:
        bars, _ = await service.ensure_sample_data(sym, tf, bars=max(limit, 300))
    if not bars:
        raise NotFoundError(f"No OHLCV available for {sym} {tf.value}")

    engine = TechnicalAnalysisEngine(
        TechnicalAnalysisConfig(swing_left=swing_left, swing_right=swing_right)
    )
    try:
        return engine.analyze(
            bars,
            symbol=sym,
            timeframe=tf.value,
            as_of_index=as_of_index,
        )
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc
