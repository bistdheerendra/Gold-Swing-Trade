"""FIXED_1R vs RISK_PERCENT equity modes (same simulator)."""

from __future__ import annotations

from app.backtest.config import RiskSizingMode
from app.backtest.equity import build_equity_curve


def test_fixed_1r_vs_risk_percent_differ_after_win() -> None:
    trades = [("t1", 1, 1.0), ("t2", 2, 1.0)]  # two +1R wins
    fixed, *_ = build_equity_curve(
        initial_equity=10_000,
        risk_fraction=0.01,
        closed_trades_net_r=trades,
        risk_mode=RiskSizingMode.FIXED_1R,
    )
    pct, *_ = build_equity_curve(
        initial_equity=10_000,
        risk_fraction=0.01,
        closed_trades_net_r=trades,
        risk_mode=RiskSizingMode.RISK_PERCENT,
    )
    # FIXED: +100 +100 = 10200
    assert fixed[-1].equity == 10_200.0
    # RISK_PERCENT compounds: 10000*1.01 = 10100; then 10100*1.01 = 10201
    assert pct[-1].equity == 10_201.0


def test_drawdown_tracked() -> None:
    trades = [("t1", 1, -1.0), ("t2", 2, -1.0)]
    curve, max_dd, max_dd_pct, _, _ = build_equity_curve(
        initial_equity=10_000,
        risk_fraction=0.01,
        closed_trades_net_r=trades,
        risk_mode=RiskSizingMode.FIXED_1R,
    )
    assert max_dd == 200.0
    assert max_dd_pct == 2.0
    assert curve[-1].equity == 9_800.0
