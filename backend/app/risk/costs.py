"""Cost engine — spread / slippage / fees / funding."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.instruments.schemas import InstrumentSpec
from app.risk.config import AccountRiskConfig, FundingCostMode, SpreadSource


class CostBreakdown(BaseModel):
    spread_cost: float = 0.0
    slippage_cost: float = 0.0
    trading_fee: float = 0.0
    funding_cost: float = 0.0
    estimated_total_cost: float = 0.0
    currency: str = "USD"
    spread_source: SpreadSource = SpreadSource.UNKNOWN
    funding_mode: FundingCostMode = FundingCostMode.UNKNOWN
    notes: list[str] = Field(default_factory=list)


def estimate_costs(
    *,
    instrument: InstrumentSpec,
    account: AccountRiskConfig,
    entry: float,
    quantity: float,
    bid: Optional[float] = None,
    ask: Optional[float] = None,
) -> CostBreakdown:
    notes: list[str] = []
    notional = quantity * instrument.contract_size * entry

    # Spread
    if bid is not None and ask is not None and ask >= bid:
        spread = ask - bid
        spread_source = SpreadSource.LIVE
    elif account.spread_source == SpreadSource.CONFIGURED:
        spread = account.estimated_spread
        spread_source = SpreadSource.CONFIGURED
        notes.append(f"Using configured estimated_spread={spread}")
    else:
        spread = 0.0
        spread_source = SpreadSource.UNKNOWN
        notes.append("Spread UNKNOWN — not assumed zero in risk narrative; cost uses 0 pending data")

    spread_cost = quantity * instrument.contract_size * spread  # round-trip approx 1x spread

    # Slippage both sides
    slip = entry * (account.slippage_pct / 100.0)
    slippage_cost = 2.0 * quantity * instrument.contract_size * slip

    fee_rate = instrument.taker_fee if account.use_taker_fees else instrument.maker_fee
    trading_fee = notional * fee_rate * 2.0  # entry + exit

    funding_cost = 0.0
    funding_mode = account.funding_mode
    if not instrument.funding_supported:
        funding_mode = FundingCostMode.ZERO
        notes.append("Instrument has no funding")
    elif funding_mode == FundingCostMode.UNKNOWN:
        notes.append("funding_status=UNKNOWN — cost not invented")
    elif funding_mode == FundingCostMode.ZERO:
        funding_cost = 0.0
    elif funding_mode == FundingCostMode.ESTIMATED:
        rate = account.estimated_funding_rate or 0.0
        funding_cost = abs(notional * rate * account.estimated_holding_intervals)
        notes.append("Funding ESTIMATED from config — not actual exchange rate")
    elif funding_mode == FundingCostMode.ACTUAL:
        rate = account.estimated_funding_rate or 0.0
        funding_cost = abs(notional * rate * account.estimated_holding_intervals)
        notes.append("Funding marked ACTUAL only if rate sourced at as_of")

    total = spread_cost + slippage_cost + trading_fee + funding_cost
    return CostBreakdown(
        spread_cost=round(spread_cost, 6),
        slippage_cost=round(slippage_cost, 6),
        trading_fee=round(trading_fee, 6),
        funding_cost=round(funding_cost, 6),
        estimated_total_cost=round(total, 6),
        currency="USD",
        spread_source=spread_source,
        funding_mode=funding_mode,
        notes=notes,
    )
