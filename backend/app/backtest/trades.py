"""Trade helpers and R-multiple calculation."""

from __future__ import annotations


def risk_points(*, bullish: bool, entry: float, stop_loss: float) -> float:
    risk = (entry - stop_loss) if bullish else (stop_loss - entry)
    return abs(risk)


def r_multiple(
    *,
    bullish: bool,
    entry: float,
    exit_price: float,
    stop_loss: float,
) -> float:
    risk = risk_points(bullish=bullish, entry=entry, stop_loss=stop_loss)
    if risk <= 0:
        return 0.0
    if bullish:
        return (exit_price - entry) / risk
    return (entry - exit_price) / risk


def cost_as_r(
    *,
    commission: float,
    risk_points_value: float,
    risk_fraction: float,
    initial_equity: float,
    equity_for_risk: float | None = None,
) -> float:
    """
    Convert flat commission into R units.
    FIXED_1R uses initial_equity; RISK_PERCENT uses equity_for_risk (current).
    """
    base = equity_for_risk if equity_for_risk is not None else initial_equity
    one_r_cash = base * risk_fraction
    if one_r_cash <= 0:
        return 0.0
    return commission / one_r_cash


def cash_pnl_from_r(
    net_r: float,
    *,
    initial_equity: float,
    risk_fraction: float,
    equity_for_risk: float | None = None,
) -> float:
    base = equity_for_risk if equity_for_risk is not None else initial_equity
    return net_r * base * risk_fraction
