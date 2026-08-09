"""Multi-timeframe analysis HTTP API (Phase 5)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Dict, List, Optional, Sequence

from fastapi import APIRouter, Depends, Query

from app.core.config import Settings, get_settings
from app.core.errors import ValidationAppError
from app.market.deps import get_market_service
from app.market.schemas import OHLCVBar, OHLCVQuery, Timeframe, ensure_utc, parse_timeframe
from app.market.service import MarketDataService
from app.mtf.analyzer import DEFAULT_TFS, MultiTimeframeAnalyzer
from app.mtf.schemas import BiasWeights, MultiTimeframeResult

router = APIRouter(prefix="/mtf", tags=["multi-timeframe"])


@router.get("/analyze", response_model=MultiTimeframeResult)
async def analyze_mtf(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    symbol: Optional[str] = Query(default=None),
    as_of: Optional[datetime] = Query(
        default=None,
        description="UTC analysis time. Defaults to now; only CLOSED candles are used.",
    ),
    timeframes: Optional[str] = Query(
        default="1d,4h,1h,30m,15m",
        description="Comma-separated timeframes",
    ),
    limit: int = Query(default=500, ge=50, le=50_000),
    ema_weight: float = Query(default=15, ge=0),
    structure_weight: float = Query(default=25, ge=0),
    bos_weight: float = Query(default=20, ge=0),
    choch_weight: float = Query(default=15, ge=0),
    momentum_weight: float = Query(default=10, ge=0),
    liquidity_weight: float = Query(default=15, ge=0),
) -> MultiTimeframeResult:
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

    weights = BiasWeights(
        ema_weight=ema_weight,
        structure_weight=structure_weight,
        bos_weight=bos_weight,
        choch_weight=choch_weight,
        momentum_weight=momentum_weight,
        liquidity_weight=liquidity_weight,
    )
    analyzer = MultiTimeframeAnalyzer(weights=weights)
    try:
        return analyzer.analyze(
            bars_by_tf,
            symbol=sym,
            as_of=as_of_utc,
            timeframes=[tf.value for tf in tf_list],
        )
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc


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
