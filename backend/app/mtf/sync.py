"""Closed-candle synchronization helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence, Tuple

from app.market.schemas import OHLCVBar, Timeframe, ensure_utc, parse_timeframe


def candle_close_time(bar: OHLCVBar, timeframe: Timeframe | str) -> datetime:
    tf = timeframe if isinstance(timeframe, Timeframe) else parse_timeframe(timeframe)
    return ensure_utc(bar.timestamp) + tf.delta


def is_candle_closed(bar: OHLCVBar, timeframe: Timeframe | str, as_of: datetime) -> bool:
    return candle_close_time(bar, timeframe) <= ensure_utc(as_of)


def last_closed_index(
    bars: Sequence[OHLCVBar],
    timeframe: Timeframe | str,
    as_of: datetime,
) -> Optional[int]:
    """
    Index of the last bar that has fully closed by `as_of`.
    Returns None if no closed candle exists.
    """
    as_of_utc = ensure_utc(as_of)
    last: Optional[int] = None
    for i, bar in enumerate(bars):
        if is_candle_closed(bar, timeframe, as_of_utc):
            last = i
        else:
            # bars are chronological; once we hit an open candle, stop
            break
    return last


def closed_window(
    bars: Sequence[OHLCVBar],
    timeframe: Timeframe | str,
    as_of: datetime,
) -> Tuple[list[OHLCVBar], Optional[int]]:
    """Return (bars_up_to_last_closed_inclusive, last_closed_index)."""
    idx = last_closed_index(bars, timeframe, as_of)
    if idx is None:
        return [], None
    return list(bars[: idx + 1]), idx
