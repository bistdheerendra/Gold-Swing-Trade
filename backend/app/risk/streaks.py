"""Loss-streak research metrics from closed trade R sequence."""

from __future__ import annotations

from typing import List, Sequence

from pydantic import BaseModel, Field


class LossStreakReport(BaseModel):
    max_consecutive_losses: int = 0
    current_consecutive_losses: int = 0
    average_loss_streak: float = 0.0
    capital_drawdown_during_max_streak: float = 0.0
    notes: List[str] = Field(default_factory=list)


def analyze_loss_streaks(
    *,
    net_r_sequence: Sequence[float],
    net_pnl_sequence: Sequence[float] | None = None,
) -> LossStreakReport:
    """net_r < 0 counts as a loss. RESEARCH metrics only."""
    max_streak = 0
    cur = 0
    streaks: List[int] = []
    max_streak_pnl_dd = 0.0
    running_pnl_in_streak = 0.0
    best_pnl_dd = 0.0

    for i, r in enumerate(net_r_sequence):
        pnl = (
            float(net_pnl_sequence[i])
            if net_pnl_sequence is not None and i < len(net_pnl_sequence)
            else float(r)
        )
        if r < 0:
            cur += 1
            running_pnl_in_streak += pnl
            max_streak = max(max_streak, cur)
            if cur == max_streak:
                best_pnl_dd = min(best_pnl_dd, running_pnl_in_streak)
                max_streak_pnl_dd = abs(best_pnl_dd) if best_pnl_dd < 0 else 0.0
        else:
            if cur > 0:
                streaks.append(cur)
            cur = 0
            running_pnl_in_streak = 0.0
            best_pnl_dd = 0.0
    if cur > 0:
        streaks.append(cur)

    avg = sum(streaks) / len(streaks) if streaks else 0.0
    return LossStreakReport(
        max_consecutive_losses=max_streak,
        current_consecutive_losses=cur,
        average_loss_streak=round(avg, 4),
        capital_drawdown_during_max_streak=round(max_streak_pnl_dd, 4),
        notes=["RESEARCH metrics from closed trades only"],
    )
