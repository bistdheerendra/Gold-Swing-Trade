"""Tests for market data repository + service (Phase 1)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import ValidationAppError
from app.market.provider import MockMarketDataProvider
from app.market.repository import InMemoryMarketDataRepository
from app.market.schemas import OHLCVBar, OHLCVQuery, Timeframe
from app.market.service import MarketDataService
from app.market.validator import OHLCVValidator


@pytest.fixture
def service() -> MarketDataService:
    return MarketDataService(
        provider=MockMarketDataProvider(),
        repository=InMemoryMarketDataRepository(),
        validator=OHLCVValidator(),
    )


@pytest.mark.asyncio
async def test_repository_upsert_and_query() -> None:
    repo = InMemoryMarketDataRepository()
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bar = OHLCVBar(
        timestamp=ts,
        symbol="XAUUSD",
        timeframe=Timeframe.H1,
        open=1,
        high=2,
        low=0.5,
        close=1.5,
        volume=10,
        source="test",
    )
    assert await repo.upsert_bars([bar]) == 1
    updated = bar.model_copy(update={"close": 1.7, "high": 2.1})
    await repo.upsert_bars([updated])
    rows = await repo.get_bars("XAUUSD", Timeframe.H1)
    assert len(rows) == 1
    assert rows[0].close == 1.7


@pytest.mark.asyncio
async def test_ingest_and_get_roundtrip(service: MarketDataService) -> None:
    start = datetime(2024, 2, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=24)
    bars, report = await service.ingest_historical("XAUUSD", "1h", start, end)
    assert report.is_valid
    assert len(bars) == 25

    stored = await service.get_ohlcv(
        OHLCVQuery(symbol="XAUUSD", timeframe=Timeframe.H1, start=start, end=end)
    )
    assert len(stored) == len(bars)
    assert stored[0].timestamp >= start
    assert stored[-1].timestamp <= end


@pytest.mark.asyncio
async def test_query_limit_returns_latest(service: MarketDataService) -> None:
    start = datetime(2024, 2, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=50)
    await service.ingest_historical("XAUUSD", "1h", start, end)
    latest = await service.get_ohlcv(
        OHLCVQuery(symbol="XAUUSD", timeframe=Timeframe.H1, limit=10)
    )
    assert len(latest) == 10
    assert latest == sorted(latest, key=lambda b: b.timestamp)


@pytest.mark.asyncio
async def test_ensure_sample_data_idempotent(service: MarketDataService) -> None:
    a, _ = await service.ensure_sample_data("XAUUSD", "1h", bars=50)
    b, _ = await service.ensure_sample_data("XAUUSD", "1h", bars=50)
    assert len(a) == len(b)
    count = await service.repository.count_bars("XAUUSD", Timeframe.H1)
    assert count >= 50


@pytest.mark.asyncio
async def test_ingest_rejects_blocking_validation() -> None:
    class BadProvider(MockMarketDataProvider):
        async def get_historical_ohlcv(self, symbol, timeframe, start, end):
            bars = await super().get_historical_ohlcv(symbol, timeframe, start, end)
            if len(bars) >= 2:
                # Force chronological violation after fetch
                return [bars[1], bars[0]]
            return bars

    svc = MarketDataService(
        provider=BadProvider(),
        repository=InMemoryMarketDataRepository(),
    )
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=3)
    with pytest.raises(ValidationAppError):
        await svc.ingest_historical("XAUUSD", "1h", start, end)
