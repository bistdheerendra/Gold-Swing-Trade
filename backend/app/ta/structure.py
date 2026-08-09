"""Market structure detection with confirmation lag (no look-ahead features)."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Sequence

from pydantic import BaseModel, Field


class SwingType(str, Enum):
    HIGH = "swing_high"
    LOW = "swing_low"


class StructureLabel(str, Enum):
    HIGHER_HIGH = "higher_high"
    HIGHER_LOW = "higher_low"
    LOWER_HIGH = "lower_high"
    LOWER_LOW = "lower_low"


class SwingPoint(BaseModel):
    """
    A confirmed swing pivot.

    pivot_index: bar index of the extremum
    confirm_index: first bar index where the swing is known (pivot_index + right)
    Features at time t may only use swings with confirm_index <= t.
    """

    type: SwingType
    pivot_index: int
    confirm_index: int
    price: float
    label: Optional[StructureLabel] = None


class StructureSnapshot(BaseModel):
    swings: List[SwingPoint] = Field(default_factory=list)
    last_swing_high: Optional[SwingPoint] = None
    last_swing_low: Optional[SwingPoint] = None
    recent_labels: List[StructureLabel] = Field(default_factory=list)


def detect_swings(
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    left: int = 2,
    right: int = 2,
    as_of_index: Optional[int] = None,
) -> List[SwingPoint]:
    """
    Fractal swing detection.

    A swing high at i requires high[i] strictly greater than highs in
    [i-left, i) and (i, i+right]. It becomes *confirmed* only at index i+right.
    When `as_of_index` is set, only swings with confirm_index <= as_of_index
    are returned — preventing look-ahead.
    """
    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")
    n = len(highs)
    if len(lows) != n:
        raise ValueError("highs and lows must be same length")
    if as_of_index is None:
        as_of_index = n - 1
    as_of_index = min(as_of_index, n - 1)

    swings: List[SwingPoint] = []
    for i in range(left, n - right):
        confirm = i + right
        if confirm > as_of_index:
            continue

        window_left_h = highs[i - left : i]
        window_right_h = highs[i + 1 : i + right + 1]
        if highs[i] > max(window_left_h) and highs[i] > max(window_right_h):
            swings.append(
                SwingPoint(
                    type=SwingType.HIGH,
                    pivot_index=i,
                    confirm_index=confirm,
                    price=float(highs[i]),
                )
            )

        window_left_l = lows[i - left : i]
        window_right_l = lows[i + 1 : i + right + 1]
        if lows[i] < min(window_left_l) and lows[i] < min(window_right_l):
            swings.append(
                SwingPoint(
                    type=SwingType.LOW,
                    pivot_index=i,
                    confirm_index=confirm,
                    price=float(lows[i]),
                )
            )

    swings.sort(key=lambda s: (s.confirm_index, s.pivot_index, s.type.value))
    return label_structure(swings)


def label_structure(swings: List[SwingPoint]) -> List[SwingPoint]:
    """Assign HH/HL/LH/LL relative to previous swing of the same type."""
    last_high: Optional[SwingPoint] = None
    last_low: Optional[SwingPoint] = None
    labeled: List[SwingPoint] = []
    for swing in swings:
        label: Optional[StructureLabel] = None
        if swing.type == SwingType.HIGH:
            if last_high is not None:
                label = (
                    StructureLabel.HIGHER_HIGH
                    if swing.price > last_high.price
                    else StructureLabel.LOWER_HIGH
                )
            last_high = swing
        else:
            if last_low is not None:
                label = (
                    StructureLabel.HIGHER_LOW
                    if swing.price > last_low.price
                    else StructureLabel.LOWER_LOW
                )
            last_low = swing
        labeled.append(swing.model_copy(update={"label": label}))
    return labeled


def structure_snapshot(
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    left: int = 2,
    right: int = 2,
    as_of_index: Optional[int] = None,
) -> StructureSnapshot:
    swings = detect_swings(
        highs, lows, left=left, right=right, as_of_index=as_of_index
    )
    last_high = next((s for s in reversed(swings) if s.type == SwingType.HIGH), None)
    last_low = next((s for s in reversed(swings) if s.type == SwingType.LOW), None)
    labels = [s.label for s in swings if s.label is not None]
    return StructureSnapshot(
        swings=swings,
        last_swing_high=last_high,
        last_swing_low=last_low,
        recent_labels=labels[-8:],
    )
