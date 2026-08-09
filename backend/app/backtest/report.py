"""Strategy analysis breakdowns — report only, no optimization."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Sequence

from app.backtest.schemas import BacktestTrade, BreakdownBucket
from app.market.schemas import ensure_utc


def _bucket_score(score: int) -> str:
    if score < 50:
        return "0-49"
    if score < 65:
        return "50-64"
    if score < 75:
        return "65-74"
    if score < 85:
        return "75-84"
    return "85-100"


def _agg(rows: Sequence[BacktestTrade]) -> BreakdownBucket:
    closed = [t for t in rows if t.net_r is not None and t.exit_reason is not None]
    wins = sum(1 for t in closed if (t.net_r or 0) > 0)
    losses = sum(1 for t in closed if (t.net_r or 0) < 0)
    net = sum(t.net_r or 0 for t in closed)
    n = len(closed)
    return BreakdownBucket(
        key="",
        trades=n,
        wins=wins,
        losses=losses,
        net_r=round(net, 6),
        win_rate=round(wins / n, 6) if n else 0.0,
    )


def build_breakdowns(trades: Sequence[BacktestTrade]) -> Dict[str, List[BreakdownBucket]]:
    by_dir: Dict[str, List[BacktestTrade]] = defaultdict(list)
    by_score: Dict[str, List[BacktestTrade]] = defaultdict(list)
    by_state: Dict[str, List[BacktestTrade]] = defaultdict(list)
    by_hour: Dict[str, List[BacktestTrade]] = defaultdict(list)
    by_dow: Dict[str, List[BacktestTrade]] = defaultdict(list)
    by_month: Dict[str, List[BacktestTrade]] = defaultdict(list)

    for t in trades:
        if t.entry_price is None:
            continue
        by_dir[t.direction].append(t)
        by_score[_bucket_score(t.score)].append(t)
        by_state[t.market_state or "UNKNOWN"].append(t)
        try:
            ts = ensure_utc(datetime.fromisoformat(t.signal_time.replace("Z", "+00:00")))
            by_hour[f"{ts.hour:02d}"].append(t)
            by_dow[ts.strftime("%A")].append(t)
            by_month[ts.strftime("%Y-%m")].append(t)
        except Exception:
            pass

    def pack(mapping: Dict[str, List[BacktestTrade]]) -> List[BreakdownBucket]:
        out: List[BreakdownBucket] = []
        for k in sorted(mapping.keys()):
            b = _agg(mapping[k])
            b.key = k
            out.append(b)
        return out

    return {
        "direction": pack(by_dir),
        "score_bucket": pack(by_score),
        "market_state": pack(by_state),
        "hour": pack(by_hour),
        "day_of_week": pack(by_dow),
        "month": pack(by_month),
    }
