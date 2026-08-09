"""Dealing range premium / discount / equilibrium."""

from __future__ import annotations

from typing import Sequence

from app.ta.structure import SwingPoint, SwingType
from app.smc.schemas import DealingRange, DealingZone, SmcConfig


def compute_dealing_range(
    swings: Sequence[SwingPoint],
    closes: Sequence[float],
    *,
    config: SmcConfig,
    as_of_index: int,
) -> DealingRange:
    known = [s for s in swings if s.confirm_index <= as_of_index]
    last_high = next((s for s in reversed(known) if s.type == SwingType.HIGH), None)
    last_low = next((s for s in reversed(known) if s.type == SwingType.LOW), None)
    if last_high is None or last_low is None or last_high.price <= last_low.price:
        return DealingRange(
            current_price=float(closes[as_of_index]) if closes else None,
            zone=DealingZone.UNKNOWN,
        )

    high = float(last_high.price)
    low = float(last_low.price)
    eq = (high + low) / 2.0
    price = float(closes[as_of_index])
    span = high - low
    position = (price - low) / span if span > 0 else 0.5
    band = config.eq_band_pct
    if abs(position - 0.5) <= band:
        zone = DealingZone.EQUILIBRIUM
    elif position > 0.5 + band:
        zone = DealingZone.PREMIUM
    else:
        zone = DealingZone.DISCOUNT

    return DealingRange(
        range_high=high,
        range_low=low,
        equilibrium=eq,
        current_price=price,
        zone=zone,
        distance_from_equilibrium=price - eq,
        high_confirm_index=last_high.confirm_index,
        low_confirm_index=last_low.confirm_index,
    )
