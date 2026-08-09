"""Equity curve and drawdown."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from app.backtest.config import RiskSizingMode
from app.backtest.schemas import EquityPoint


def build_equity_curve(
    *,
    initial_equity: float,
    risk_fraction: float,
    closed_trades_net_r: Sequence[Tuple[str, int, float]],
    risk_mode: RiskSizingMode = RiskSizingMode.FIXED_1R,
) -> Tuple[List[EquityPoint], float, float, Optional[str], Optional[str]]:
    """
    closed_trades_net_r: list of (timestamp, bar_index, net_r) in order.

    FIXED_1R: equity += net_r * (initial_equity * risk_fraction)
    RISK_PERCENT: equity += net_r * (current_equity * risk_fraction)  [compounds]
    """
    equity = initial_equity
    peak = initial_equity
    points: List[EquityPoint] = [
        EquityPoint(
            timestamp="",
            bar_index=-1,
            equity=initial_equity,
            drawdown=0.0,
            drawdown_pct=0.0,
            peak=peak,
        )
    ]
    max_dd = 0.0
    max_dd_pct = 0.0
    dd_start: Optional[str] = None
    dd_end: Optional[str] = None
    peak_ts: Optional[str] = None

    for ts, idx, net_r in closed_trades_net_r:
        if risk_mode == RiskSizingMode.RISK_PERCENT:
            one_r = equity * risk_fraction
        else:
            one_r = initial_equity * risk_fraction
        equity = equity + net_r * one_r
        if equity > peak:
            peak = equity
            peak_ts = ts
        dd = peak - equity
        dd_pct = (dd / peak * 100.0) if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd_pct
            dd_start = peak_ts
            dd_end = ts
        points.append(
            EquityPoint(
                timestamp=ts,
                bar_index=idx,
                equity=round(equity, 4),
                drawdown=round(dd, 4),
                drawdown_pct=round(dd_pct, 4),
                peak=round(peak, 4),
            )
        )
    return points, max_dd, max_dd_pct, dd_start, dd_end
