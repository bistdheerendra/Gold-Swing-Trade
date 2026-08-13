"""Delta India market provider — live smoke + mapping tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.market.delta_provider import DeltaIndiaMarketDataProvider
from app.market.schemas import Timeframe


@pytest.mark.asyncio
async def test_delta_symbol_map() -> None:
    p = DeltaIndiaMarketDataProvider()
    assert p.map_symbol("PAXGUSD") == "PAXGUSD"
    assert p.map_symbol("slvonusd") == "SLVONUSD"
    with pytest.raises(ValueError):
        p.map_symbol("BTCUSD")
    with pytest.raises(ValueError):
        p.map_symbol("XAUUSD")


def test_delta_base_url_normalizes_v2() -> None:
    """Host-only DELTA_INDIA_BASE_URL must still hit /v2/tickers (not 404)."""
    host_only = DeltaIndiaMarketDataProvider(
        base_url="https://api.india.delta.exchange"
    )
    assert host_only.base_url.endswith("/v2")
    already = DeltaIndiaMarketDataProvider(
        base_url="https://api.india.delta.exchange/v2"
    )
    assert already.base_url == "https://api.india.delta.exchange/v2"


@pytest.mark.asyncio
async def test_delta_live_candles_and_ticker() -> None:
    """Requires network — skip if Delta unreachable."""
    p = DeltaIndiaMarketDataProvider()
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=30)
    try:
        bars = await p.get_historical_ohlcv("PAXGUSD", Timeframe.H1, start, end)
        ticker = await p.get_ticker("PAXGUSD")
    except (httpx.HTTPError, RuntimeError) as exc:
        pytest.skip(f"Delta India unreachable: {exc}")

    assert len(bars) >= 5
    assert bars[0].timestamp <= bars[-1].timestamp
    assert bars[-1].source == "delta_india"
    assert bars[-1].close > 0
    assert ticker["spread_source"] == "LIVE"
    assert ticker["bid"] is not None or ticker["last"] is not None
