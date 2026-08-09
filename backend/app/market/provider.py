"""Market data provider abstraction and mock implementation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from math import sin
from typing import List, Optional

from app.market.schemas import OHLCVBar, Timeframe, ensure_utc, parse_timeframe
from app.market.validator import clip_to_range


class MarketDataProvider(ABC):
    """
    Vendor-agnostic historical OHLCV source.

    Strategy / ML layers must depend on this interface (or repository),
    never on a concrete broker SDK.
    """

    name: str = "abstract"

    @abstractmethod
    async def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str | Timeframe,
        start: datetime,
        end: datetime,
    ) -> List[OHLCVBar]:
        """Return bars in [start, end] inclusive. Must not return future-of-end bars."""


class MockMarketDataProvider(MarketDataProvider):
    """
    Deterministic synthetic gold-like series for offline development.

    Supports XAUUSD and PAXGUSD (and any symbol with a configured mock base).
    Seeded from timestamps so tests are reproducible. No look-ahead.
    """

    name = "mock"

    def __init__(self, base_price: float | None = None) -> None:
        from app.market.symbols import mock_base_price

        self.base_price = base_price if base_price is not None else mock_base_price("XAUUSD")

    async def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str | Timeframe,
        start: datetime,
        end: datetime,
    ) -> List[OHLCVBar]:
        from app.market.symbols import mock_base_price

        tf = timeframe if isinstance(timeframe, Timeframe) else parse_timeframe(timeframe)
        start_utc = ensure_utc(start)
        end_utc = ensure_utc(end)
        if end_utc < start_utc:
            raise ValueError("end must be >= start")

        symbol_norm = symbol.strip().upper()
        step = tf.delta
        cursor = _align_timestamp(start_utc, tf)
        bars: List[OHLCVBar] = []
        # Per-symbol base so PAXGUSD ≠ XAUUSD series (slightly different path)
        prev_close = mock_base_price(symbol_norm)

        # Hard cap prevents accidental huge ranges in tests/API misuse
        max_bars = 20_000
        while cursor <= end_utc and len(bars) < max_bars:
            bar = self._synthesize_bar(
                symbol=symbol_norm,
                timeframe=tf,
                timestamp=cursor,
                prev_close=prev_close,
            )
            bars.append(bar)
            prev_close = bar.close
            cursor = cursor + step

        # Safety: clip again so nothing outside the requested window leaks through
        return clip_to_range(bars, start_utc, end_utc)

    def _synthesize_bar(
        self,
        *,
        symbol: str,
        timeframe: Timeframe,
        timestamp: datetime,
        prev_close: float,
    ) -> OHLCVBar:
        # Deterministic pseudo-random walk from unix epoch seconds.
        # Scale absolute moves with price so % volatility stays similar to the
        # original ~2300 mock (needed for ML direction labels / thresholds).
        scale = max(prev_close, 1.0) / 2300.0
        epoch = int(timestamp.timestamp())
        wave = sin(epoch / 3600.0) * 4.0 * scale
        drift = ((epoch // int(timeframe.delta.total_seconds())) % 17) * 0.15 * scale
        open_price = round(prev_close, 3)
        close_price = round(prev_close + wave * 0.15 + (drift - 1.2 * scale) * 0.05, 3)
        wick = abs(wave) * 0.08 + 0.4 * scale
        high = round(max(open_price, close_price) + wick, 3)
        low = round(min(open_price, close_price) - wick, 3)
        volume = float(1000 + (epoch % 500))
        return OHLCVBar(
            timestamp=timestamp,
            symbol=symbol,
            timeframe=timeframe,
            open=open_price,
            high=high,
            low=low,
            close=close_price,
            volume=volume,
            source=self.name,
        )


def _align_timestamp(ts: datetime, timeframe: Timeframe) -> datetime:
    """Align to candle open boundary (UTC). Forward-align if not exact."""
    ts = ensure_utc(ts)
    if timeframe == Timeframe.D1:
        aligned = datetime(ts.year, ts.month, ts.day, tzinfo=timezone.utc)
        return aligned if aligned >= ts else aligned + timeframe.delta

    seconds = int(timeframe.delta.total_seconds())
    epoch = int(ts.timestamp())
    aligned_epoch = epoch - (epoch % seconds)
    aligned = datetime.fromtimestamp(aligned_epoch, tz=timezone.utc)
    if aligned < ts:
        aligned = aligned + timeframe.delta
    return aligned


def default_range_for_timeframe(
    timeframe: Timeframe,
    *,
    end: Optional[datetime] = None,
    bars: int = 200,
) -> tuple[datetime, datetime]:
    end_utc = ensure_utc(end or datetime.now(timezone.utc))
    start_utc = end_utc - (timeframe.delta * bars)
    return start_utc, end_utc
