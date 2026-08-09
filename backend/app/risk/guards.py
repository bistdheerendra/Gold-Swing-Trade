"""Daily loss + consecutive loss guards."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.risk.config import AccountRiskConfig


class DailyRiskState(BaseModel):
    starting_daily_equity: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    consecutive_losses: int = 0


class GuardResult(BaseModel):
    ok: bool
    status: str = "OK"
    reasons: list[str] = Field(default_factory=list)


def check_daily_and_streak(
    account: AccountRiskConfig, state: DailyRiskState
) -> GuardResult:
    reasons = []
    day_pnl = state.realized_pnl + state.unrealized_pnl
    limit = -abs(state.starting_daily_equity * account.max_daily_loss_pct / 100.0)
    if day_pnl <= limit:
        return GuardResult(
            ok=False,
            status="DAILY_LIMIT_REACHED",
            reasons=[
                f"Daily loss {day_pnl:.2f} reached limit {limit:.2f} "
                f"({account.max_daily_loss_pct}% of starting equity)"
            ],
        )
    if state.consecutive_losses >= account.max_consecutive_losses:
        return GuardResult(
            ok=False,
            status="TRADING_BLOCKED",
            reasons=[
                f"consecutive_losses={state.consecutive_losses} >= "
                f"max {account.max_consecutive_losses}"
            ],
        )
    return GuardResult(ok=True, status="OK", reasons=reasons)
