"""Account / risk configuration (Phase 11)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FundingCostMode(str, Enum):
    ZERO = "ZERO"
    ESTIMATED = "ESTIMATED"
    ACTUAL = "ACTUAL"
    UNKNOWN = "UNKNOWN"


class SpreadSource(str, Enum):
    LIVE = "LIVE"
    CONFIGURED = "CONFIGURED"
    UNKNOWN = "UNKNOWN"


class AccountRiskConfig(BaseModel):
    account_balance: float = 30_000.0
    available_balance: Optional[float] = None
    currency: str = "INR"
    # Convert INR risk → USD instrument PnL (research). Mark as CONFIGURED.
    usd_inr_rate: float = Field(default=83.0, description="INR per 1 USD — CONFIGURED")
    risk_per_trade_pct: float = Field(default=1.0, ge=0.01, le=10.0)
    max_daily_loss_pct: float = Field(default=3.0, ge=0.1, le=50.0)
    max_total_exposure_pct: float = Field(default=30.0, ge=1.0, le=100.0)
    max_open_positions: int = 3
    max_consecutive_losses: int = 4
    default_leverage: float = 5.0
    maximum_leverage: float = 20.0  # research cap below exchange max
    minimum_margin_buffer_pct: float = 20.0
    minimum_rr: float = 1.5
    max_stop_distance_pct: float = 5.0
    min_stop_ticks: int = 5
    estimated_spread: float = 0.5  # price units USD
    spread_source: SpreadSource = SpreadSource.CONFIGURED
    slippage_pct: float = 0.02  # 0.02% of price per side
    funding_mode: FundingCostMode = FundingCostMode.UNKNOWN
    estimated_funding_rate: Optional[float] = None  # per interval, if ESTIMATED
    estimated_holding_intervals: float = 1.0
    use_taker_fees: bool = True

    def available(self) -> float:
        return self.available_balance if self.available_balance is not None else self.account_balance

    def risk_amount_account(self) -> float:
        return self.account_balance * self.risk_per_trade_pct / 100.0

    def risk_amount_usd(self) -> float:
        amt = self.risk_amount_account()
        if self.currency.upper() == "USD":
            return amt
        return amt / max(self.usd_inr_rate, 1e-9)

    def to_account_ccy(self, usd: float) -> float:
        if self.currency.upper() == "USD":
            return usd
        return usd * self.usd_inr_rate
