"""Unit tests for Binance futures research provider."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.market.binance_provider import BinanceFuturesMarketDataProvider
from app.market.schemas import Timeframe


@pytest.mark.asyncio
async def test_binance_klines_maps_to_paxgusdt_bars() -> None:
    provider = BinanceFuturesMarketDataProvider()
    # one kline row: open time ms, o,h,l,c,volume, ...
    row = [
        int(datetime(2025, 4, 1, 12, 0, tzinfo=timezone.utc).timestamp() * 1000),
        "3000.0",
        "3010.0",
        "2990.0",
        "3005.0",
        "12.5",
        0,
        "0",
        1,
        "0",
        "0",
        "0",
    ]
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = [row]

    with patch(
        "app.market.binance_provider._request_with_backoff",
        new=AsyncMock(return_value=mock_resp),
    ):
        bars = await provider.get_historical_ohlcv(
            "PAXGUSDT",
            Timeframe.M15,
            datetime(2025, 4, 1, tzinfo=timezone.utc),
            datetime(2025, 4, 2, tzinfo=timezone.utc),
        )
    assert len(bars) == 1
    assert bars[0].symbol == "PAXGUSDT"
    assert bars[0].source == "binance_futures"
    assert bars[0].close == 3005.0


@pytest.mark.asyncio
async def test_binance_rejects_paxgusd_symbol() -> None:
    provider = BinanceFuturesMarketDataProvider()
    with pytest.raises(ValueError, match="only supports"):
        await provider.get_historical_ohlcv(
            "PAXGUSD",
            "15m",
            datetime(2025, 4, 1, tzinfo=timezone.utc),
            datetime(2025, 4, 2, tzinfo=timezone.utc),
        )
