"""Simple risk-of-ruin research estimator — RESEARCH ESTIMATE ONLY."""

from __future__ import annotations

from pydantic import BaseModel


class RuinEstimate(BaseModel):
    label: str = "RESEARCH ESTIMATE ONLY"
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    risk_pct: float
    edge_per_trade_r: float
    rough_ruin_hint: str
    notes: list[str]


def estimate_risk_of_ruin(
    *,
    win_rate: float,
    avg_win_r: float = 1.5,
    avg_loss_r: float = 1.0,
    risk_pct: float = 1.0,
) -> RuinEstimate:
    """
    Toy estimator: edge = p*W - (1-p)*L in R units.
    Does NOT claim mathematical certainty; does not auto-block trades.
    """
    p = max(0.0, min(1.0, win_rate))
    edge = p * avg_win_r - (1 - p) * avg_loss_r
    if edge <= 0:
        hint = "Negative/zero edge at these assumptions — high ruin risk if persistent"
    elif risk_pct >= 5:
        hint = "Edge positive but high risk% — drawdowns can still be severe"
    else:
        hint = "Positive edge under assumptions — still not a guarantee"
    return RuinEstimate(
        win_rate=p,
        avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r,
        risk_pct=risk_pct,
        edge_per_trade_r=round(edge, 4),
        rough_ruin_hint=hint,
        notes=[
            "RESEARCH ESTIMATE ONLY",
            "Not used to auto-block trades unless explicitly configured later",
        ],
    )
