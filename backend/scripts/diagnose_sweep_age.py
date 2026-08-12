#!/usr/bin/env python3
"""Diagnose bars since last directional liquidity sweep (research)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.backtest.data import parse_csv_ohlcv  # noqa: E402
from app.smc.engine import SmcEngine  # noqa: E402
from app.smc.schemas import SmcDirection  # noqa: E402
from app.strategy.config import StrategyConfig  # noqa: E402


def load(tf: str):
    path = REPO_ROOT / "data" / "historical" / f"PAXGUSD_{tf}.csv"
    return parse_csv_ohlcv(path, symbol="PAXGUSD", timeframe=tf, source="real_delta_india")


def last_sweep(smc, want: SmcDirection):
    sweeps = [
        s
        for s in smc.liquidity_sweeps
        if s.valid and s.direction == want and s.confirm_index <= smc.as_of_index
    ]
    return sweeps[-1] if sweeps else None


def report(tf: str, bars, cfg: StrategyConfig) -> None:
    window = bars[-min(len(bars), 500) :]
    smc = SmcEngine().analyze(window, symbol="PAXGUSD", timeframe=tf)
    lookback = cfg.recent_sweep_bars
    as_of = smc.as_of_index
    last_ts = window[-1].timestamp.isoformat()

    print(f"\n=== {tf}  (as_of_index={as_of}, last_bar={last_ts}, n={len(window)}) ===")
    print(f"Rule lookback recent_sweep_bars = {lookback}")
    print(f"Total valid sweeps in window: {sum(1 for s in smc.liquidity_sweeps if s.valid)}")

    for label, want in (("BUY needs BULLISH sweep", SmcDirection.BULLISH), ("SELL needs BEARISH sweep", SmcDirection.BEARISH)):
        s = last_sweep(smc, want)
        if s is None:
            print(f"  {label}: NONE in full window - miss for entire series slice")
            continue
        age = as_of - s.confirm_index
        in_window = age <= lookback
        ts = window[s.confirm_index].timestamp.isoformat() if 0 <= s.confirm_index < len(window) else "?"
        print(
            f"  {label}: last confirm_index={s.confirm_index} @ {ts} | "
            f"age={age} bars | inside {lookback}? {in_window} | "
            f"level={s.liquidity_level:.2f}"
        )


def main() -> None:
    cfg = StrategyConfig()
    print("PAXGUSD liquidity-sweep age diagnose (historical CSV)")
    print(f"strategy recent_sweep_bars={cfg.recent_sweep_bars} entry_confirm_bars={cfg.entry_confirm_bars}")
    for tf in ("1h", "15m"):
        bars = load(tf)
        report(tf, bars, cfg)


if __name__ == "__main__":
    main()
