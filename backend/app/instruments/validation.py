"""Instrument / trade geometry validation."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.instruments.schemas import InstrumentSpec
from app.strategy.schemas import SignalDirection, TakeProfitLevel


class StopLossValidationResult(BaseModel):
    ok: bool
    reasons: List[str] = Field(default_factory=list)
    stop_distance: Optional[float] = None
    stop_distance_pct: Optional[float] = None


class TargetValidationResult(BaseModel):
    ok: bool
    reasons: List[str] = Field(default_factory=list)


def validate_stop_loss(
    *,
    direction: SignalDirection,
    entry: float,
    stop_loss: float,
    instrument: InstrumentSpec,
    min_stop_distance: float = 0.0,
    max_stop_distance_pct: float = 10.0,
) -> StopLossValidationResult:
    reasons: List[str] = []
    if entry <= 0 or stop_loss <= 0:
        return StopLossValidationResult(ok=False, reasons=["Entry/SL must be positive"])
    if abs(entry - stop_loss) < instrument.tick_size / 2:
        return StopLossValidationResult(ok=False, reasons=["SL equals entry (zero risk)"])

    # Tick alignment
    rem = round(stop_loss / instrument.tick_size) * instrument.tick_size
    if abs(rem - stop_loss) > 1e-9:
        reasons.append(
            f"SL {stop_loss} not aligned to tick_size {instrument.tick_size} (will round)"
        )

    if direction == SignalDirection.BUY:
        if stop_loss >= entry:
            return StopLossValidationResult(
                ok=False, reasons=["BUY requires stop_loss < entry"]
            )
        dist = entry - stop_loss
    elif direction == SignalDirection.SELL:
        if stop_loss <= entry:
            return StopLossValidationResult(
                ok=False, reasons=["SELL requires stop_loss > entry"]
            )
        dist = stop_loss - entry
    else:
        return StopLossValidationResult(
            ok=False, reasons=[f"Cannot size risk for direction {direction.value}"]
        )

    pct = dist / entry * 100.0
    if dist < max(min_stop_distance, instrument.tick_size):
        return StopLossValidationResult(
            ok=False,
            reasons=[f"Stop distance {dist} too small vs tick/min"],
            stop_distance=dist,
            stop_distance_pct=pct,
        )
    if pct > max_stop_distance_pct:
        return StopLossValidationResult(
            ok=False,
            reasons=[f"Stop distance {pct:.2f}% exceeds max {max_stop_distance_pct}%"],
            stop_distance=dist,
            stop_distance_pct=pct,
        )
    return StopLossValidationResult(
        ok=True, reasons=reasons, stop_distance=dist, stop_distance_pct=round(pct, 6)
    )


def validate_targets(
    *,
    direction: SignalDirection,
    entry: float,
    targets: List[TakeProfitLevel],
) -> TargetValidationResult:
    if not targets:
        return TargetValidationResult(ok=False, reasons=["No targets provided"])
    prices = [t.price for t in targets]
    reasons: List[str] = []
    if direction == SignalDirection.BUY:
        if any(p <= entry for p in prices):
            return TargetValidationResult(ok=False, reasons=["BUY targets must be > entry"])
        if prices != sorted(prices):
            reasons.append("BUY targets should be ascending TP1<TP2<TP3")
            return TargetValidationResult(ok=False, reasons=reasons)
    elif direction == SignalDirection.SELL:
        if any(p >= entry for p in prices):
            return TargetValidationResult(ok=False, reasons=["SELL targets must be < entry"])
        if prices != sorted(prices, reverse=True):
            reasons.append("SELL targets should be descending TP1>TP2>TP3")
            return TargetValidationResult(ok=False, reasons=reasons)
    else:
        return TargetValidationResult(ok=False, reasons=["Invalid direction for targets"])
    return TargetValidationResult(ok=True, reasons=reasons)
