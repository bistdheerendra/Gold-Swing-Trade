"""Tests for mock market data provider (Phase 1)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.market.provider import MockMarketDataProvider
from app.market.schemas import Timeframe


@pytest.mark.asyncio
async def test_mock_provider_respects_range_and_timeframe() -> None:
    provider = MockMarketDataProvider(base_price=2300.0)
    start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, 5, 0, tzinfo=timezone.utc)
    bars = await provider.get_historical_ohlcv("XAUUSD", Timeframe.H1, start, end)

    assert len(bars) == 6  # 00..05 inclusive
    assert all(start <= b.timestamp <= end for b in bars)
    assert all(b.symbol == "XAUUSD" for b in bars)
    assert all(b.timeframe == Timeframe.H1 for b in bars)
    assert all(b.source == "mock" for b in bars)
    # Strictly ascending — no look-ahead shuffle
    timestamps = [b.timestamp for b in bars]
    assert timestamps == sorted(timestamps)


@pytest.mark.asyncio
async def test_mock_provider_deterministic() -> None:
    provider = MockMarketDataProvider()
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=10)
    a = await provider.get_historical_ohlcv("XAUUSD", "1h", start, end)
    b = await provider.get_historical_ohlcv("XAUUSD", "1h", start, end)
    assert [x.model_dump() for x in a] == [y.model_dump() for y in b]


@pytest.mark.asyncio
async def test_mock_provider_all_supported_timeframes() -> None:
    provider = MockMarketDataProvider()
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for tf in Timeframe:
        end = start + tf.delta * 5
        bars = await provider.get_historical_ohlcv("XAUUSD", tf, start, end)
        assert len(bars) >= 5
        assert bars[0].timeframe == tf


@pytest.mark.asyncio
async def test_mock_provider_rejects_inverted_range() -> None:
    provider = MockMarketDataProvider()
    start = datetime(2024, 1, 2, tzinfo=timezone.utc)
    end = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        await provider.get_historical_ohlcv("XAUUSD", "1h", start, end)


@pytest.mark.asyncio
async def test_no_bars_beyond_end() -> None:
    """Look-ahead guard: provider must not emit candles after end."""
    provider = MockMarketDataProvider()
    start = datetime(2024, 3, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 3, 1, 3, 0, tzinfo=timezone.utc)
    bars = await provider.get_historical_ohlcv("XAUUSD", Timeframe.H1, start, end)
    assert max(b.timestamp for b in bars) <= end
