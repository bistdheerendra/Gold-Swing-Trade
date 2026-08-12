"""Binance USDT-M futures OHLCV — research-only (not Delta PAXGUSD)."""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.market.provider import MarketDataProvider
from app.market.real_provider import _request_with_backoff
from app.market.schemas import OHLCVBar, Timeframe, ensure_utc, parse_timeframe
from app.market.validator import clip_to_range, sort_bars

logger = logging.getLogger(__name__)

BINANCE_FUTURES_BASE = "https://fapi.binance.com"
DEFAULT_BINANCE_PAXGUSDT = "PAXGUSDT"
_BINANCE_MAX_KLINES = 1500

_INTERVAL: Dict[Timeframe, str] = {
    Timeframe.M15: "15m",
    Timeframe.M30: "30m",
    Timeframe.H1: "1h",
    Timeframe.H4: "4h",
    Timeframe.D1: "1d",
}


def _align_timestamp(ts: datetime, tf: Timeframe) -> datetime:
    from app.market.provider import _align_timestamp as _align

    return _align(ts, tf)


class BinanceFuturesMarketDataProvider(MarketDataProvider):
    """
    Public Binance Futures klines for PAXGUSDT perpetual.

    Research sidecar only — never alias bars to PAXGUSD / Delta.
    No API key required for klines.
    """

    name = "binance_futures"

    def __init__(
        self,
        *,
        base_url: str = BINANCE_FUTURES_BASE,
        symbol: str = DEFAULT_BINANCE_PAXGUSDT,
        timeout_seconds: float = 30.0,
        min_request_interval: float = 0.12,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.symbol = symbol.strip().upper()
        self.timeout = timeout_seconds
        self.min_request_interval = min_request_interval
        self._last_request_at = 0.0

    async def _throttle(self) -> None:
        now = time.monotonic()
        wait = self.min_request_interval - (now - self._last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_at = time.monotonic()

    async def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str | Timeframe,
        start: datetime,
        end: datetime,
    ) -> List[OHLCVBar]:
        app_symbol = symbol.strip().upper()
        if app_symbol not in (self.symbol, "PAXGUSDT"):
            raise ValueError(
                f"Binance research provider only supports {self.symbol}, got {app_symbol}"
            )
        tf = timeframe if isinstance(timeframe, Timeframe) else parse_timeframe(timeframe)
        if tf not in _INTERVAL:
            raise ValueError(f"Unsupported timeframe for Binance research: {tf}")

        start_utc = ensure_utc(start)
        end_utc = ensure_utc(end)
        if end_utc < start_utc:
            raise ValueError("end must be >= start")

        bars = await self._fetch_klines(app_symbol, tf, start_utc, end_utc)
        return clip_to_range(sort_bars(bars), start_utc, end_utc)

    async def _fetch_klines(
        self,
        app_symbol: str,
        tf: Timeframe,
        start_utc: datetime,
        end_utc: datetime,
    ) -> List[OHLCVBar]:
        interval = _INTERVAL[tf]
        step_ms = int(tf.delta.total_seconds() * 1000)
        start_ms = int(_align_timestamp(start_utc, tf).timestamp() * 1000)
        end_ms = int(end_utc.timestamp() * 1000)
        url = f"{self.base_url}/fapi/v1/klines"

        by_ts: Dict[int, Dict[str, Any]] = {}
        cursor_end = end_ms

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for _ in range(80):
                cursor_start = max(
                    start_ms,
                    cursor_end - (_BINANCE_MAX_KLINES * step_ms),
                )
                await self._throttle()
                params = {
                    "symbol": self.symbol,
                    "interval": interval,
                    "startTime": cursor_start,
                    "endTime": cursor_end,
                    "limit": _BINANCE_MAX_KLINES,
                }
                resp = await _request_with_backoff(
                    client,
                    "GET",
                    url,
                    params=params,
                    headers={"Accept": "application/json"},
                )
                if resp.status_code >= 400:
                    raise RuntimeError(
                        f"Binance klines HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                chunk = resp.json()
                if not isinstance(chunk, list) or not chunk:
                    break
                for row in chunk:
                    if not isinstance(row, list) or len(row) < 6:
                        raise RuntimeError(f"Malformed Binance kline: {row!r}")
                    ts = int(row[0])
                    o, h, l, c = float(row[1]), float(row[2]), float(row[3]), float(row[4])
                    vol = float(row[5] or 0.0)
                    if h < max(o, c) or l > min(o, c) or h < l:
                        raise RuntimeError(f"Invalid OHLC in Binance kline: {row!r}")
                    by_ts[ts] = {
                        "time": ts,
                        "open": o,
                        "high": h,
                        "low": l,
                        "close": c,
                        "volume": vol,
                    }
                oldest = min(int(r[0]) for r in chunk)
                if oldest <= start_ms:
                    break
                cursor_end = oldest - 1
                if cursor_end <= start_ms:
                    break

        bars: List[OHLCVBar] = []
        for ts in sorted(by_ts):
            row = by_ts[ts]
            bars.append(
                OHLCVBar(
                    timestamp=datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc),
                    symbol=app_symbol,
                    timeframe=tf,
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=max(0.0, row["volume"]),
                    source=self.name,
                )
            )
        return bars
