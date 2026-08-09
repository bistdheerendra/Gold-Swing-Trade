"""3-candle Fair Value Gap detection with lifecycle."""

from __future__ import annotations

from typing import List, Sequence

from app.smc.schemas import (
    FvgEvent,
    FvgLifecycle,
    SmcConfig,
    SmcDirection,
    SmcEventType,
)


def detect_fvgs(
    highs: Sequence[float],
    lows: Sequence[float],
    *,
    timeframe: str,
    config: SmcConfig,
    as_of_index: int,
) -> List[FvgEvent]:
    events: List[FvgEvent] = []
    n = as_of_index + 1
    for i in range(2, n):
        if lows[i] > highs[i - 2]:
            gap_low = float(highs[i - 2])
            gap_high = float(lows[i])
            size = gap_high - gap_low
            if size >= config.fvg_min_size:
                events.append(
                    FvgEvent(
                        id=f"{SmcEventType.BULLISH_FVG.value}:{timeframe}:{i}",
                        type=SmcEventType.BULLISH_FVG,
                        direction=SmcDirection.BULLISH,
                        timeframe=timeframe,
                        created_index=i,
                        confirm_index=i,
                        high=gap_high,
                        low=gap_low,
                        size=size,
                        lifecycle=FvgLifecycle.ACTIVE,
                        filled=False,
                        valid=True,
                    )
                )
        if highs[i] < lows[i - 2]:
            gap_high = float(lows[i - 2])
            gap_low = float(highs[i])
            size = gap_high - gap_low
            if size >= config.fvg_min_size:
                events.append(
                    FvgEvent(
                        id=f"{SmcEventType.BEARISH_FVG.value}:{timeframe}:{i}",
                        type=SmcEventType.BEARISH_FVG,
                        direction=SmcDirection.BEARISH,
                        timeframe=timeframe,
                        created_index=i,
                        confirm_index=i,
                        high=gap_high,
                        low=gap_low,
                        size=size,
                        lifecycle=FvgLifecycle.ACTIVE,
                        filled=False,
                        valid=True,
                    )
                )

    for event in events:
        _apply_fill(event, highs, lows, as_of_index)
    return events


def _apply_fill(
    event: FvgEvent,
    highs: Sequence[float],
    lows: Sequence[float],
    as_of_index: int,
) -> None:
    assert event.high is not None and event.low is not None
    partial = False
    for t in range(event.created_index + 1, as_of_index + 1):
        intersects = lows[t] <= event.high and highs[t] >= event.low
        if event.direction == SmcDirection.BULLISH:
            filled = lows[t] <= event.low
        else:
            filled = highs[t] >= event.high
        if filled:
            event.filled = True
            event.fill_index = t
            event.lifecycle = FvgLifecycle.FILLED
            event.valid = False
            event.metadata["invalidated"] = True
            return
        if intersects:
            partial = True
    if partial:
        event.lifecycle = FvgLifecycle.PARTIALLY_FILLED
