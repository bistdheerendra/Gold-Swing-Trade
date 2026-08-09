"""Market data HTTP API (Phase 1 + Phase 11.5 real data)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.errors import ValidationAppError
from app.market.deps import get_market_service
from app.market.real_provider import get_provider_health
from app.market.schemas import OHLCVBar, OHLCVQuery, Timeframe, ValidationReport, parse_timeframe
from app.market.service import MarketDataService
from app.market.symbols import SymbolListResponse, list_symbols, normalize_symbol

router = APIRouter(prefix="/market", tags=["market"])

# Bars enough for MTF lookback + ML train/val/test windows
_DEFAULT_BACKFILL_BARS: dict[str, int] = {
    "15m": 4000,
    "30m": 3000,
    "1h": 2000,
    "4h": 1000,
    "1d": 500,
}


def _tf(value: str) -> Timeframe:
    try:
        return parse_timeframe(value)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc


class IngestRequest(BaseModel):
    symbol: Optional[str] = None
    timeframe: str = "1h"
    start: datetime
    end: datetime
    persist: bool = True


class IngestResponse(BaseModel):
    symbol: str
    timeframe: str
    bars_ingested: int
    validation: ValidationReport
    sample: List[OHLCVBar] = Field(default_factory=list)


class BackfillRequest(BaseModel):
    symbols: List[str] = Field(default_factory=lambda: ["PAXGUSD", "XAUUSD"])
    timeframes: List[str] = Field(
        default_factory=lambda: ["15m", "30m", "1h", "4h", "1d"]
    )
    bars: Optional[dict[str, int]] = None
    end: Optional[datetime] = None
    persist: bool = True


class BackfillSymbolResult(BaseModel):
    symbol: str
    timeframe: str
    bars_ingested: int
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    source: Optional[str] = None
    ok: bool = True
    error: Optional[str] = None


class BackfillResponse(BaseModel):
    provider: str
    store: str
    results: List[BackfillSymbolResult]
    note: str = (
        "Real historical backfill — no mock fallback. "
        "Prefer MARKET_DATA_STORE=postgres for durable ML datasets."
    )


class OHLCVListResponse(BaseModel):
    symbol: str
    timeframe: str
    count: int
    bars: List[OHLCVBar]


class MarketStatusResponse(BaseModel):
    provider: str
    store: str
    symbol: str
    supported_timeframes: List[str]
    counts: dict[str, int]
    allow_mock_data: bool = False
    provider_ok: bool = True
    last_error: Optional[str] = None


@router.get("/symbols", response_model=SymbolListResponse)
async def market_symbols(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SymbolListResponse:
    """List research tradeable symbols (XAUUSD, PAXGUSD, …)."""
    return SymbolListResponse(
        default_symbol=normalize_symbol(settings.market_symbol),
        symbols=list_symbols(),
    )


@router.get("/status", response_model=MarketStatusResponse)
async def market_status(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MarketStatusResponse:
    symbol = settings.market_symbol
    counts: dict[str, int] = {}
    for tf in Timeframe:
        counts[tf.value] = await service.repository.count_bars(symbol, tf)
    health = get_provider_health()
    return MarketStatusResponse(
        provider=settings.market_data_provider,
        store=settings.market_data_store,
        symbol=symbol,
        supported_timeframes=[tf.value for tf in Timeframe],
        counts=counts,
        allow_mock_data=settings.allow_mock_data,
        provider_ok=bool(health.get("ok", True)),
        last_error=health.get("last_error"),
    )


@router.get("/ohlcv", response_model=OHLCVListResponse)
async def get_ohlcv(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    timeframe: str = Query(default="1h"),
    symbol: Optional[str] = Query(default=None),
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
    limit: Optional[int] = Query(default=500, ge=1, le=50_000),
) -> OHLCVListResponse:
    tf = _tf(timeframe)
    sym = (symbol or settings.market_symbol).upper()
    bars = await service.get_ohlcv(
        OHLCVQuery(symbol=sym, timeframe=tf, start=start, end=end, limit=limit)
    )
    return OHLCVListResponse(
        symbol=sym,
        timeframe=tf.value,
        count=len(bars),
        bars=bars,
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_ohlcv(
    body: IngestRequest,
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> IngestResponse:
    sym = (body.symbol or settings.market_symbol).upper()
    tf = _tf(body.timeframe)
    bars, report = await service.ingest_historical(
        symbol=sym,
        timeframe=tf,
        start=body.start,
        end=body.end,
        persist=body.persist,
    )
    if len(bars) <= 6:
        sample = bars
    else:
        sample = bars[:3] + bars[-3:]
    return IngestResponse(
        symbol=sym,
        timeframe=tf.value,
        bars_ingested=len(bars),
        validation=report,
        sample=sample,
    )


@router.post("/backfill", response_model=BackfillResponse)
async def backfill_historical(
    body: BackfillRequest,
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BackfillResponse:
    """
    Pull real historical OHLCV for configured symbols/timeframes.

    Covers MTF lookback + ML train/val/test windows. Never falls back to mock.
    """
    if settings.market_data_provider.lower().strip() == "mock":
        raise ValidationAppError(
            "Refusing backfill with MARKET_DATA_PROVIDER=mock. "
            "Use binance or twelvedata."
        )

    end = body.end or datetime.now(timezone.utc)
    bar_counts = dict(_DEFAULT_BACKFILL_BARS)
    if body.bars:
        bar_counts.update({k: int(v) for k, v in body.bars.items()})

    results: List[BackfillSymbolResult] = []
    for sym in body.symbols:
        symbol = sym.strip().upper()
        for tf_raw in body.timeframes:
            tf = _tf(tf_raw)
            n_bars = bar_counts.get(tf.value, 500)
            start = end - (tf.delta * n_bars)
            try:
                bars, _report = await service.ingest_historical(
                    symbol=symbol,
                    timeframe=tf,
                    start=start,
                    end=end,
                    persist=body.persist,
                )
                results.append(
                    BackfillSymbolResult(
                        symbol=symbol,
                        timeframe=tf.value,
                        bars_ingested=len(bars),
                        start=bars[0].timestamp if bars else start,
                        end=bars[-1].timestamp if bars else end,
                        source=bars[-1].source if bars else None,
                        ok=True,
                    )
                )
            except Exception as exc:  # noqa: BLE001 — per-symbol failure, no mock
                results.append(
                    BackfillSymbolResult(
                        symbol=symbol,
                        timeframe=tf.value,
                        bars_ingested=0,
                        start=start,
                        end=end,
                        ok=False,
                        error=str(exc),
                    )
                )

    if not any(r.ok for r in results):
        raise ValidationAppError(
            "Backfill failed for all symbol/timeframe pairs: "
            + "; ".join(f"{r.symbol}/{r.timeframe}: {r.error}" for r in results[:4])
        )

    return BackfillResponse(
        provider=settings.market_data_provider,
        store=settings.market_data_store,
        results=results,
    )


@router.post("/seed", response_model=IngestResponse)
async def seed_sample_data(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    timeframe: str = Query(default="1h"),
    symbol: Optional[str] = Query(default=None),
    bars: int = Query(default=300, ge=10, le=5000),
    force: bool = Query(
        default=False,
        description="Clear existing bars and re-fetch from active provider",
    ),
) -> IngestResponse:
    """Ensure OHLCV history from the configured real provider."""
    if settings.market_data_provider.lower().strip() == "mock" and not settings.allow_mock_data:
        raise ValidationAppError(
            "MARKET_DATA_PROVIDER=mock is blocked without ALLOW_MOCK_DATA=true"
        )
    sym = (symbol or settings.market_symbol).upper()
    tf = _tf(timeframe)
    loaded, report = await service.ensure_sample_data(sym, tf, bars=bars, force=force)
    return IngestResponse(
        symbol=sym,
        timeframe=tf.value,
        bars_ingested=len(loaded),
        validation=report,
        sample=loaded[:5],
    )


@router.post("/refresh", response_model=IngestResponse)
async def refresh_market_data(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    timeframe: str = Query(default="1h"),
    symbol: Optional[str] = Query(default=None),
    bars: int = Query(default=400, ge=10, le=5000),
) -> IngestResponse:
    """Force refresh latest candles from live provider."""
    sym = (symbol or settings.market_symbol).upper()
    tf = _tf(timeframe)
    loaded, report = await service.refresh_ohlcv(sym, tf, bars=bars)
    return IngestResponse(
        symbol=sym,
        timeframe=tf.value,
        bars_ingested=len(loaded),
        validation=report,
        sample=loaded[-5:] if loaded else [],
    )


@router.get("/ticker")
async def market_ticker(
    settings: Annotated[Settings, Depends(get_settings)],
    symbol: Optional[str] = Query(default=None),
) -> dict:
    """
    Live bid/ask/last from Delta India when provider=delta_india.
    Otherwise last close from the configured real provider.
    """
    sym = (symbol or settings.market_symbol).upper()
    provider_name = settings.market_data_provider.lower().strip().replace("-", "_")

    from app.market.deps import get_provider

    provider = get_provider()
    try:
        if provider_name in ("delta_india", "delta") and hasattr(provider, "get_ticker"):
            return await provider.get_ticker(sym)
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=6)
        bars = await provider.get_historical_ohlcv(sym, Timeframe.H1, start, end)
    except Exception as exc:  # noqa: BLE001
        raise ValidationAppError(f"Ticker fetch failed: {exc}") from exc

    if not bars:
        raise ValidationAppError(f"No recent bars for ticker on {sym}")
    last = bars[-1]
    return {
        "symbol": sym,
        "bid": None,
        "ask": None,
        "last": last.close,
        "mark_price": last.close,
        "spread_source": "UNKNOWN",
        "source": last.source,
        "bar_timestamp": last.timestamp.isoformat(),
        "note": "Last close from real OHLCV provider (not a live order book)",
    }
