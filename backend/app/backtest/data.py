"""Historical data adapters — CSV + in-app market provider."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Protocol, Sequence

from app.market.schemas import OHLCVBar, Timeframe, ensure_utc, parse_timeframe


class HistoricalDataAdapter(Protocol):
    async def load(
        self,
        symbol: str,
        timeframe: str,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[OHLCVBar]:
        ...


def parse_csv_ohlcv(
    path: str | Path,
    *,
    symbol: str,
    timeframe: str,
    source: str = "csv",
) -> List[OHLCVBar]:
    """
    Expected CSV columns (header required):

        timestamp,open,high,low,close[,volume]

    timestamp: ISO-8601 (prefer UTC, e.g. 2024-01-01T00:00:00Z)
    volume: optional — missing/blank → 0.0
    """
    tf = parse_timeframe(timeframe)
    rows: List[OHLCVBar] = []
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise ValueError("CSV has no header")
        fields = {f.strip().lower(): f for f in reader.fieldnames}
        required = ["timestamp", "open", "high", "low", "close"]
        for req in required:
            if req not in fields:
                raise ValueError(f"CSV missing required column: {req}")
        vol_key = fields.get("volume")
        for line_no, row in enumerate(reader, start=2):
            ts_raw = row[fields["timestamp"]].strip()
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            ts = ensure_utc(ts)
            vol_raw = row.get(vol_key, "") if vol_key else ""
            volume = float(vol_raw) if vol_raw not in ("", None) else 0.0
            rows.append(
                OHLCVBar(
                    timestamp=ts,
                    symbol=symbol.upper(),
                    timeframe=tf,
                    open=float(row[fields["open"]]),
                    high=float(row[fields["high"]]),
                    low=float(row[fields["low"]]),
                    close=float(row[fields["close"]]),
                    volume=max(0.0, volume),
                    source=source,
                )
            )
    rows.sort(key=lambda b: b.timestamp)
    return rows


class CsvHistoricalAdapter:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    async def load(
        self,
        symbol: str,
        timeframe: str,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[OHLCVBar]:
        bars = parse_csv_ohlcv(self.path, symbol=symbol, timeframe=timeframe)
        if start:
            start_u = ensure_utc(start)
            bars = [b for b in bars if b.timestamp >= start_u]
        if end:
            end_u = ensure_utc(end)
            bars = [b for b in bars if b.timestamp <= end_u]
        if limit is not None:
            bars = bars[-limit:]
        return bars


class ProviderHistoricalAdapter:
    """Loads from MarketDataService / mock provider already used by the app."""

    def __init__(self, service) -> None:
        self.service = service

    async def load(
        self,
        symbol: str,
        timeframe: str,
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[OHLCVBar]:
        from app.market.schemas import OHLCVQuery

        tf = parse_timeframe(timeframe)
        lim = limit or 2000
        bars = await self.service.get_ohlcv(
            OHLCVQuery(symbol=symbol.upper(), timeframe=tf, start=start, end=end, limit=lim)
        )
        if not bars:
            bars, _ = await self.service.ensure_sample_data(
                symbol.upper(), tf, bars=max(lim, 300)
            )
        out = list(bars)
        if start:
            start_u = ensure_utc(start)
            out = [b for b in out if ensure_utc(b.timestamp) >= start_u]
        if end:
            end_u = ensure_utc(end)
            out = [b for b in out if ensure_utc(b.timestamp) <= end_u]
        return out


def filter_bars_range(
    bars: Sequence[OHLCVBar],
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> List[OHLCVBar]:
    out = list(bars)
    if start:
        start_u = ensure_utc(start)
        out = [b for b in out if ensure_utc(b.timestamp) >= start_u]
    if end:
        end_u = ensure_utc(end)
        out = [b for b in out if ensure_utc(b.timestamp) <= end_u]
    return out
