"""Margin / exposure checks."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.instruments.schemas import InstrumentSpec
from app.risk.config import AccountRiskConfig


class MarginResult(BaseModel):
    leverage: float
    required_margin_usd: float
    required_margin_account: float
    available_balance: float
    buffer_ok: bool
    exposure_ok: bool
    leverage_ok: bool
    ok: bool
    reasons: list[str] = Field(default_factory=list)


def check_margin(
    *,
    instrument: InstrumentSpec,
    account: AccountRiskConfig,
    notional_usd: float,
    leverage: float,
) -> MarginResult:
    reasons = []
    lev = leverage
    if lev <= 0:
        return MarginResult(
            leverage=lev,
            required_margin_usd=0,
            required_margin_account=0,
            available_balance=account.available(),
            buffer_ok=False,
            exposure_ok=False,
            leverage_ok=False,
            ok=False,
            reasons=["Leverage must be > 0"],
        )
    max_lev = min(account.maximum_leverage, instrument.max_leverage)
    leverage_ok = lev <= max_lev + 1e-9
    if not leverage_ok:
        reasons.append(f"Leverage {lev} exceeds research max {max_lev}")

    required_usd = notional_usd / lev
    required_acct = account.to_account_ccy(required_usd)
    avail = account.available()
    buffer_floor = avail * (account.minimum_margin_buffer_pct / 100.0)
    usable = avail - buffer_floor
    buffer_ok = required_acct <= usable + 1e-9
    if not buffer_ok:
        reasons.append(
            f"INSUFFICIENT_MARGIN / MARGIN_LIMIT: need {required_acct:.2f} "
            f"{account.currency} but usable after {account.minimum_margin_buffer_pct}% "
            f"buffer is {usable:.2f}. Reduce quantity (do not raise leverage)."
        )

    max_notional_acct = account.account_balance * (account.max_total_exposure_pct / 100.0)
    # Effective exposure for leveraged perps = required margin (not full notional).
    exposure_ok = required_acct <= max_notional_acct + 1e-9
    if not exposure_ok:
        reasons.append(
            f"POSITION_LIMIT_EXCEEDED: required margin {required_acct:.2f} > "
            f"{account.max_total_exposure_pct}% of balance ({max_notional_acct:.2f}). "
            f"Reduce quantity (do not raise leverage)."
        )

    ok = leverage_ok and buffer_ok and exposure_ok
    return MarginResult(
        leverage=lev,
        required_margin_usd=round(required_usd, 4),
        required_margin_account=round(required_acct, 4),
        available_balance=avail,
        buffer_ok=buffer_ok,
        exposure_ok=exposure_ok,
        leverage_ok=leverage_ok,
        ok=ok,
        reasons=reasons,
    )
