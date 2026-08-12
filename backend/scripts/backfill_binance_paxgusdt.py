#!/usr/bin/env python3
"""Backfill Binance PAXGUSDT perpetual CSVs — research only (never overwrites PAXGUSD)."""

from __future__ import annotations

import asyncio
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.market.binance_provider import BinanceFuturesMarketDataProvider  # noqa: E402
from app.market.schemas import ANALYSIS_TIMEFRAMES, Timeframe  # noqa: E402


def _log(msg: str) -> None:
    print(msg, flush=True)


def _write_csv(path: Path, bars: List[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["timestamp", "open", "high", "low", "close", "volume", "source"],
        )
        w.writeheader()
        for b in bars:
            w.writerow(
                {
                    "timestamp": b.timestamp.isoformat(),
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                    "source": b.source,
                }
            )


async def main_async() -> int:
    settings = get_settings()
    provider = BinanceFuturesMarketDataProvider(
        base_url=settings.binance_futures_base_url,
        symbol=settings.binance_paxgusdt_symbol,
    )
    out_dir = REPO_ROOT / "data" / "historical"
    end = datetime.now(timezone.utc)
    # Listing ~2025-03-27; request generously
    start = end - timedelta(days=800)
    info: Dict[str, Any] = {}
    symbol = settings.binance_paxgusdt_symbol
    _log(f"=== Binance research backfill {symbol} ===")
    for tf_key in ANALYSIS_TIMEFRAMES:
        tf = Timeframe(tf_key)
        bars = await provider.get_historical_ohlcv(symbol, tf, start, end)
        path = out_dir / f"{symbol}_{tf.value}.csv"
        if path.name.startswith("PAXGUSD_"):
            raise RuntimeError("Refusing to write Delta PAXGUSD path from Binance backfill")
        _write_csv(path, bars)
        info[tf.value] = {
            "bars": len(bars),
            "first": bars[0].timestamp.isoformat() if bars else None,
            "last": bars[-1].timestamp.isoformat() if bars else None,
            "csv": path.name,
        }
        _log(f"  {tf.value}: n={len(bars)} -> {path.name}")
    _log(f"Done: {info}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main_async()))
