"""Delta Exchange India — public OHLCV provider (no API keys)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.market.provider import MarketDataProvider, _align_timestamp
from app.market.schemas import OHLCVBar, Timeframe, ensure_utc, parse_timeframe, sort_bars
from app.market.validator import clip_to_range

DELTA_INDIA_BASE = "https://api.india.delta.exchange/v2"

# App symbol → Delta product symbol (public candles; no auth)
_SYMBOL_MAP: Dict[str, str] = {
    "PAXGUSD": "PAXGUSD",
    # Spot-style research alias: use PAX Gold perpetual as live gold proxy
    "XAUUSD": "PAXGUSD",
}

_RESOLUTION: Dict[Timeframe, str] = {
    Timeframe.M15: "15m",
    Timeframe.M30: "30m",
    Timeframe.H1: "1h",
    Timeframe.H4: "4h",
    Timeframe.D1: "1d",
}

# Delta docs: ~2000–4000 candles per request — stay conservative
_MAX_CANDLES_PER_REQUEST = 2000


class DeltaIndiaMarketDataProvider(MarketDataProvider):
    """
    Live/historical OHLCV from Delta Exchange India public REST API.

    No API key required for candles/tickers.
    Does not place orders.
    """

    name = "delta_india"

    def __init__(
        self,
        *,
        base_url: str = DELTA_INDIA_BASE,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds

    def map_symbol(self, symbol: str) -> str:
        key = symbol.strip().upper()
        if key not in _SYMBOL_MAP:
            raise ValueError(
                f"Delta provider does not support symbol '{symbol}'. "
                f"Supported: {', '.join(sorted(_SYMBOL_MAP))}"
            )
        return _SYMBOL_MAP[key]

    async def get_historical_ohlcv(
        self,
        symbol: str,
        timeframe: str | Timeframe,
        start: datetime,
        end: datetime,
    ) -> List[OHLCVBar]:
        tf = timeframe if isinstance(timeframe, Timeframe) else parse_timeframe(timeframe)
        start_utc = ensure_utc(start)
        end_utc = ensure_utc(end)
        if end_utc < start_utc:
            raise ValueError("end must be >= start")

        app_symbol = symbol.strip().upper()
        delta_symbol = self.map_symbol(app_symbol)
        resolution = _RESOLUTION[tf]
        step_sec = int(tf.delta.total_seconds())

        # Align window; fetch newest first in chunks walking backward if needed
        aligned_start = _align_timestamp(start_utc, tf)
        end_epoch = int(end_utc.timestamp())
        start_epoch = int(aligned_start.timestamp())

        raw_rows: List[Dict[str, Any]] = []
        cursor_end = end_epoch
        # Walk backward until we cover start (or hit empty)
        for _ in range(20):
            cursor_start = max(
                start_epoch,
                cursor_end - (_MAX_CANDLES_PER_REQUEST * step_sec),
            )
            chunk = await self._fetch_candles(
                delta_symbol, resolution, cursor_start, cursor_end
            )
            if not chunk:
                break
            raw_rows.extend(chunk)
            oldest = min(int(r["time"]) for r in chunk)
            if oldest <= start_epoch:
                break
            cursor_end = oldest - 1
            if cursor_end <= start_epoch:
                break

        by_ts: Dict[int, Dict[str, Any]] = {}
        for row in raw_rows:
            by_ts[int(row["time"])] = row

        bars: List[OHLCVBar] = []
        for ts, row in sorted(by_ts.items()):
            bars.append(
                OHLCVBar(
                    timestamp=datetime.fromtimestamp(ts, tz=timezone.utc),
                    symbol=app_symbol,
                    timeframe=tf,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row.get("volume") or 0.0),
                    source=self.name,
                )
            )
        return clip_to_range(sort_bars(bars), start_utc, end_utc)

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """Read-only live ticker (bid/ask/mark). No auth."""
        app_symbol = symbol.strip().upper()
        delta_symbol = self.map_symbol(app_symbol)
        url = f"{self.base_url}/tickers/{delta_symbol}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(url, headers={"Accept": "application/json"})
            resp.raise_for_status()
            payload = resp.json()
        result = payload.get("result") or {}
        quotes = result.get("quotes") or {}
        bid = _f(quotes.get("best_bid") or result.get("close"))
        ask = _f(quotes.get("best_ask") or result.get("close"))
        last = _f(result.get("close") or result.get("mark_price"))
        return {
            "symbol": app_symbol,
            "delta_symbol": delta_symbol,
            "bid": bid,
            "ask": ask,
            "last": last,
            "mark_price": _f(result.get("mark_price")),
            "spread_source": "LIVE" if bid is not None and ask is not None else "UNKNOWN",
            "source": self.name,
            "raw_time": result.get("time"),
        }

    async def _fetch_candles(
        self,
        delta_symbol: str,
        resolution: str,
        start_epoch: int,
        end_epoch: int,
    ) -> List[Dict[str, Any]]:
        params = {
            "symbol": delta_symbol,
            "resolution": resolution,
            "start": start_epoch,
            "end": end_epoch,
        }
        url = f"{self.base_url}/history/candles"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(
                url, params=params, headers={"Accept": "application/json"}
            )
            resp.raise_for_status()
            payload = resp.json()
        if not payload.get("success", True):
            raise RuntimeError(f"Delta candles error: {payload}")
        result = payload.get("result") or []
        if not isinstance(result, list):
            raise RuntimeError(f"Unexpected Delta candles payload: {type(result)}")
        return result


def _f(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
