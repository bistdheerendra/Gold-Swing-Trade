"""Position sizing — risk / stop distance / contract size."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.instruments.schemas import InstrumentSpec
from app.risk.config import AccountRiskConfig


class PositionSizeResult(BaseModel):
    risk_amount_account: float
    risk_amount_usd: float
    loss_per_unit_usd: float
    raw_quantity: float
    rounded_quantity: float
    rounding_difference: float
    notional_usd: float
    ok: bool = True
    reasons: list[str] = Field(default_factory=list)


def size_position(
    *,
    instrument: InstrumentSpec,
    account: AccountRiskConfig,
    entry: float,
    stop_distance: float,
) -> PositionSizeResult:
    risk_acct = account.risk_amount_account()
    risk_usd = account.risk_amount_usd()
    # 1 quantity loses: contract_size * stop_distance (USD for vanilla PAXGUSD)
    loss_per_unit = instrument.contract_size * stop_distance
    if loss_per_unit <= 0:
        return PositionSizeResult(
            risk_amount_account=risk_acct,
            risk_amount_usd=risk_usd,
            loss_per_unit_usd=0.0,
            raw_quantity=0.0,
            rounded_quantity=0.0,
            rounding_difference=0.0,
            notional_usd=0.0,
            ok=False,
            reasons=["loss_per_unit_at_SL is zero"],
        )

    raw = risk_usd / loss_per_unit
    rounded = instrument.round_quantity(raw, mode="down")
    reasons = []
    if rounded < instrument.minimum_quantity:
        return PositionSizeResult(
            risk_amount_account=risk_acct,
            risk_amount_usd=risk_usd,
            loss_per_unit_usd=loss_per_unit,
            raw_quantity=raw,
            rounded_quantity=rounded,
            rounding_difference=raw - rounded,
            notional_usd=0.0,
            ok=False,
            reasons=[
                f"Quantity {rounded} below minimum {instrument.minimum_quantity} "
                f"(raw={raw:.4f}). Reduce SL distance or increase risk/account."
            ],
        )
    if rounded > instrument.maximum_quantity:
        rounded = instrument.maximum_quantity
        reasons.append(f"Clamped to maximum_quantity {instrument.maximum_quantity}")

    notional = rounded * instrument.contract_size * entry
    return PositionSizeResult(
        risk_amount_account=round(risk_acct, 4),
        risk_amount_usd=round(risk_usd, 6),
        loss_per_unit_usd=round(loss_per_unit, 8),
        raw_quantity=round(raw, 6),
        rounded_quantity=rounded,
        rounding_difference=round(raw - rounded, 6),
        notional_usd=round(notional, 4),
        ok=True,
        reasons=reasons,
    )
