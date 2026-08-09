"""Performance metrics from closed trades."""

from __future__ import annotations

from typing import Optional, Sequence

from app.backtest.schemas import BacktestTrade, PerformanceMetrics, TradeLifecycle


def compute_metrics(
    trades: Sequence[BacktestTrade],
    *,
    total_signals: int,
    signals_expired: int,
    initial_equity: float,
    equity_final: float,
    max_drawdown: float,
    max_drawdown_pct: float,
    max_drawdown_start: Optional[str],
    max_drawdown_end: Optional[str],
) -> PerformanceMetrics:
    closed = [
        t
        for t in trades
        if t.net_r is not None
        and t.exit_reason is not None
        and t.status
        not in (TradeLifecycle.EXPIRED, TradeLifecycle.AMBIGUOUS_SKIP, TradeLifecycle.PENDING)
    ]

    wins = [t for t in closed if (t.net_r or 0) > 1e-9]
    losses = [t for t in closed if (t.net_r or 0) < -1e-9]
    flat = [t for t in closed if abs(t.net_r or 0) <= 1e-9]

    gross_profit = sum(t.net_r or 0 for t in wins)
    gross_loss = abs(sum(t.net_r or 0 for t in losses))
    net = sum(t.net_r or 0 for t in closed)
    n = len(closed)
    win_rate = (len(wins) / n) if n else 0.0
    avg_win = (gross_profit / len(wins)) if wins else 0.0
    avg_loss = (gross_loss / len(losses)) if losses else 0.0
    avg_r = (net / n) if n else 0.0
    loss_rate = (len(losses) / n) if n else 0.0
    expectancy = win_rate * avg_win - loss_rate * avg_loss
    pf = (gross_profit / gross_loss) if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)

    durations = [t.duration_bars for t in closed if t.duration_bars is not None]
    avg_dur = (sum(durations) / len(durations)) if durations else 0.0
    total_cost = sum(t.trading_cost or 0 for t in closed)
    total_cost_r = sum(t.trading_cost_r or 0 for t in closed)

    w_streak = l_streak = max_w = max_l = 0
    for t in closed:
        r = t.net_r or 0
        if r > 0:
            w_streak += 1
            l_streak = 0
            max_w = max(max_w, w_streak)
        elif r < 0:
            l_streak += 1
            w_streak = 0
            max_l = max(max_l, l_streak)
        else:
            w_streak = l_streak = 0

    entered = sum(1 for t in trades if t.entry_price is not None)

    return PerformanceMetrics(
        total_signals=total_signals,
        signals_expired=signals_expired,
        trades_entered=entered,
        winning_trades=len(wins),
        losing_trades=len(losses),
        breakeven_trades=len(flat),
        win_rate=round(win_rate, 6),
        gross_profit_r=round(gross_profit, 6),
        gross_loss_r=round(gross_loss, 6),
        net_profit_r=round(net, 6),
        average_win_r=round(avg_win, 6),
        average_loss_r=round(avg_loss, 6),
        average_r=round(avg_r, 6),
        expectancy_r=round(expectancy, 6),
        profit_factor=round(min(pf, 999.0), 6),
        max_drawdown=round(max_drawdown, 4),
        max_drawdown_pct=round(max_drawdown_pct, 4),
        max_drawdown_start=max_drawdown_start,
        max_drawdown_end=max_drawdown_end,
        longest_winning_streak=max_w,
        longest_losing_streak=max_l,
        average_trade_duration_bars=round(avg_dur, 4),
        total_trading_cost=round(total_cost, 4),
        total_trading_cost_r=round(total_cost_r, 6),
        final_equity=round(equity_final, 4),
        initial_equity=initial_equity,
    )
