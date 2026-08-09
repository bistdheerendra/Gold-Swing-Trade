"""BOS / CHoCH detection with explicit state machine."""

from __future__ import annotations

from typing import List, Sequence, Tuple

from app.ta.structure import StructureLabel, SwingPoint, SwingType
from app.smc.breaks import is_bearish_break, is_bullish_break
from app.smc.schemas import BosEvent, SmcConfig, SmcDirection, SmcEventType


def infer_initial_bias(swings: Sequence[SwingPoint]) -> SmcDirection:
    highs = [s for s in swings if s.type == SwingType.HIGH]
    lows = [s for s in swings if s.type == SwingType.LOW]
    if len(highs) < 2 or len(lows) < 2:
        return SmcDirection.NEUTRAL
    h1, h2 = highs[-2], highs[-1]
    l1, l2 = lows[-2], lows[-1]
    bull = h2.label == StructureLabel.HIGHER_HIGH and l2.label == StructureLabel.HIGHER_LOW
    bear = h2.label == StructureLabel.LOWER_HIGH and l2.label == StructureLabel.LOWER_LOW
    if bull and not bear:
        return SmcDirection.BULLISH
    if bear and not bull:
        return SmcDirection.BEARISH
    return SmcDirection.NEUTRAL


def detect_bos_choch(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    swings: Sequence[SwingPoint],
    *,
    timeframe: str,
    config: SmcConfig,
    as_of_index: int,
) -> Tuple[List[BosEvent], List[BosEvent], SmcDirection]:
    """
    Walk forward bar-by-bar.
    Against-bias first break → CHoCH; with-bias / after flip continuation → BOS.
    """
    bos_events: List[BosEvent] = []
    choch_events: List[BosEvent] = []
    bias = SmcDirection.NEUTRAL
    broken_high_pivots: set[int] = set()
    broken_low_pivots: set[int] = set()

    for t in range(as_of_index + 1):
        known = [s for s in swings if s.confirm_index <= t]
        if bias == SmcDirection.NEUTRAL:
            bias = infer_initial_bias(known)

        active_high = _latest_unbroken(known, SwingType.HIGH, broken_high_pivots)
        active_low = _latest_unbroken(known, SwingType.LOW, broken_low_pivots)

        # Bullish break of swing high
        if active_high is not None and t >= active_high.confirm_index:
            if is_bullish_break(
                high=highs[t], close=closes[t], level=active_high.price, config=config
            ):
                direction = SmcDirection.BULLISH
                is_choch = bias == SmcDirection.BEARISH
                event = _make_break_event(
                    direction=direction,
                    timeframe=timeframe,
                    t=t,
                    swing=active_high,
                    as_choch=is_choch,
                )
                if is_choch:
                    choch_events.append(event)
                    bias = SmcDirection.BULLISH
                else:
                    bos_events.append(event)
                    bias = SmcDirection.BULLISH
                broken_high_pivots.add(active_high.pivot_index)

        # Bearish break of swing low
        if active_low is not None and t >= active_low.confirm_index:
            if is_bearish_break(
                low=lows[t], close=closes[t], level=active_low.price, config=config
            ):
                direction = SmcDirection.BEARISH
                is_choch = bias == SmcDirection.BULLISH
                event = _make_break_event(
                    direction=direction,
                    timeframe=timeframe,
                    t=t,
                    swing=active_low,
                    as_choch=is_choch,
                )
                if is_choch:
                    choch_events.append(event)
                    bias = SmcDirection.BEARISH
                else:
                    bos_events.append(event)
                    bias = SmcDirection.BEARISH
                broken_low_pivots.add(active_low.pivot_index)

    return bos_events, choch_events, bias


def _latest_unbroken(
    swings: Sequence[SwingPoint],
    swing_type: SwingType,
    broken: set[int],
) -> SwingPoint | None:
    for swing in reversed(swings):
        if swing.type == swing_type and swing.pivot_index not in broken:
            return swing
    return None


def _make_break_event(
    *,
    direction: SmcDirection,
    timeframe: str,
    t: int,
    swing: SwingPoint,
    as_choch: bool,
) -> BosEvent:
    etype = SmcEventType.CHOCH if as_choch else SmcEventType.BOS
    return BosEvent(
        id=f"{etype.value}:{timeframe}:{t}:{swing.pivot_index}",
        type=etype,
        direction=direction,
        timeframe=timeframe,
        created_index=swing.pivot_index,
        confirm_index=t,
        break_index=t,
        broken_level=swing.price,
        source_swing_index=swing.pivot_index,
        price=swing.price,
        high=swing.price if swing.type == SwingType.HIGH else None,
        low=swing.price if swing.type == SwingType.LOW else None,
        valid=True,
        metadata={"as_choch": as_choch},
    )
