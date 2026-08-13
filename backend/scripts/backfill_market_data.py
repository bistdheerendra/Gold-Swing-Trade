#!/usr/bin/env python3
"""
Phase 11.5 / 11.12 — one-time / repeatable real OHLCV historical backfill.

Pulls free-tier candles for PAXGUSD + SLVONUSD across 15m/30m/1h/4h/1d,
validates via OHLCVValidator, upserts into the configured repository
(prefer MARKET_DATA_STORE=postgres), and also writes CSV snapshots under
data/historical/ for durable ML re-runs.

Series are stored separately per symbol — never merge PAXGUSD and SLVONUSD.

Usage (from backend/):
  python scripts/backfill_market_data.py
  python scripts/backfill_market_data.py --symbols SLVONUSD --timeframes 15m,30m,1h,4h,1d
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure backend package root is on path when run as a script
BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database import get_db_session  # noqa: E402
from app.market.deps import get_provider, get_memory_repository, reset_market_singletons  # noqa: E402
from app.market.repository import PostgresMarketDataRepository  # noqa: E402
from app.market.schemas import Timeframe, parse_timeframe  # noqa: E402
from app.market.service import MarketDataService  # noqa: E402
from app.market.validator import OHLCVValidator  # noqa: E402

DEFAULT_BARS = {
    "15m": 4000,
    "30m": 3000,
    "1h": 2000,
    "4h": 1000,
    "1d": 500,
}


def _write_csv(path: Path, bars) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "source",
            ],
        )
        writer.writeheader()
        for bar in bars:
            writer.writerow(
                {
                    "timestamp": bar.timestamp.isoformat(),
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                    "volume": bar.volume,
                    "source": bar.source,
                }
            )


async def _build_service() -> MarketDataService:
    settings = get_settings()
    reset_market_singletons()
    get_settings.cache_clear()
    settings = get_settings()
    provider = get_provider()
    store = settings.market_data_store.lower().strip()
    if store == "postgres":
        async for session in get_db_session():
            repo = PostgresMarketDataRepository(session)
            return MarketDataService(provider=provider, repository=repo)
        raise RuntimeError("Could not open Postgres session")
    return MarketDataService(
        provider=provider,
        repository=get_memory_repository(),
        validator=OHLCVValidator(),
    )


async def run_backfill(
    symbols: list[str],
    timeframes: list[str],
    bars_by_tf: dict[str, int],
) -> int:
    settings = get_settings()
    if settings.market_data_provider.lower().strip() == "mock":
        print(
            "ERROR: Refusing to backfill with MARKET_DATA_PROVIDER=mock. "
            "Set MARKET_DATA_PROVIDER=binance (or twelvedata).",
            file=sys.stderr,
        )
        return 2

    service = await _build_service()
    end = datetime.now(timezone.utc)
    out_dir = REPO_ROOT / "data" / "historical"
    failures = 0

    print(
        f"Backfill provider={settings.market_data_provider} "
        f"store={settings.market_data_store} end={end.isoformat()}"
    )

    for symbol in symbols:
        for tf_raw in timeframes:
            tf = parse_timeframe(tf_raw)
            n = bars_by_tf.get(tf.value, 500)
            start = end - (tf.delta * n)
            print(f"  -> {symbol} {tf.value} bars~={n} ...", end=" ", flush=True)
            try:
                bars, report = await service.ingest_historical(
                    symbol, tf, start, end, persist=True
                )
                csv_path = out_dir / f"{symbol}_{tf.value}.csv"
                _write_csv(csv_path, bars)
                missing = len(report.missing_timestamps)
                print(
                    f"ok bars={len(bars)} missing_gaps={missing} "
                    f"source={bars[-1].source if bars else '?'} csv={csv_path.name}"
                )
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"FAILED: {exc}")

    if failures:
        print(f"Completed with {failures} failure(s). No mock fallback was used.")
        return 1
    print("Backfill complete.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Real market data historical backfill")
    parser.add_argument(
        "--symbols",
        default="PAXGUSD,SLVONUSD",
        help="Comma-separated symbols",
    )
    parser.add_argument(
        "--timeframes",
        default="15m,30m,1h,4h,1d",
        help="Comma-separated timeframes",
    )
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    timeframes = [t.strip() for t in args.timeframes.split(",") if t.strip()]
    code = asyncio.run(run_backfill(symbols, timeframes, DEFAULT_BARS))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
