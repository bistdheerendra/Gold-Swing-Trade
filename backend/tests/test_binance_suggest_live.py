"""Live Binance suggest wiring — research sidecar."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.market.schemas import OHLCVBar, Timeframe
from app.research.binance_suggest import (
    load_binance_bars_live,
    suggest_from_binance_async,
)


def _bar(ts: datetime, close: float = 4400.0) -> OHLCVBar:
    return OHLCVBar(
        timestamp=ts,
        symbol="PAXGUSDT",
        timeframe=Timeframe.M15,
        open=close - 1,
        high=close + 2,
        low=close - 2,
        close=close,
        volume=10.0,
        source="binance_futures",
    )


@pytest.mark.asyncio
async def test_load_binance_bars_live_uses_provider() -> None:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    bars = [_bar(now - timedelta(minutes=15 * i), 4400 + i) for i in range(5, 0, -1)]

    async def fake_ohlcv(symbol, timeframe, start, end):
        tf = timeframe if isinstance(timeframe, Timeframe) else Timeframe(str(timeframe))
        return [
            OHLCVBar(
                timestamp=b.timestamp,
                symbol="PAXGUSDT",
                timeframe=tf,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                source="binance_futures",
            )
            for b in bars
        ]

    with patch(
        "app.research.binance_suggest.BinanceFuturesMarketDataProvider"
    ) as provider_cls:
        provider_cls.return_value.get_historical_ohlcv = AsyncMock(side_effect=fake_ohlcv)
        out = await load_binance_bars_live(limit=5)

    assert "15m" in out
    assert len(out["15m"]) == 5
    assert out["15m"][-1].close == 4401.0


@pytest.mark.asyncio
async def test_suggest_async_falls_back_to_csv_on_live_failure() -> None:
    with patch(
        "app.research.binance_suggest.load_binance_bars_live",
        new=AsyncMock(side_effect=RuntimeError("network down")),
    ), patch(
        "app.research.binance_suggest.suggest_from_binance",
        return_value={
            "enabled": True,
            "live": False,
            "live_warning": "Live Binance fetch failed — using CSV: network down",
            "signal": "WAIT",
        },
    ) as sync_suggest:
        result = await suggest_from_binance_async(live=True)

    assert result["live"] is False
    assert result["live_warning"]
    sync_suggest.assert_called_once()
    assert sync_suggest.call_args.kwargs.get("live") is False
