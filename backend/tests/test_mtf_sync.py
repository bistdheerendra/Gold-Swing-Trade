"""Closed-candle sync tests (Phase 5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.market.schemas import OHLCVBar, Timeframe
from app.mtf.sync import candle_close_time, is_candle_closed, last_closed_index


def _bar(open_ts: datetime) -> OHLCVBar:
    return OHLCVBar(
        timestamp=open_ts,
        symbol="XAUUSD",
        timeframe=Timeframe.H1,
        open=1,
        high=2,
        low=0.5,
        close=1.5,
        volume=1,
        source="test",
    )


def test_candle_close_time_h1() -> None:
    open_ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert candle_close_time(_bar(open_ts), Timeframe.H1) == open_ts + timedelta(hours=1)


def test_unfinished_htf_candle_excluded() -> None:
    # 15m as_of at 13:15 means 13:00 15m closed; 13:00 1h still open until 14:00
    bars = [
        _bar(datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)),
        _bar(datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)),
        _bar(datetime(2024, 1, 1, 13, 0, tzinfo=timezone.utc)),  # open — not closed at 13:15
    ]
    as_of = datetime(2024, 1, 1, 13, 15, tzinfo=timezone.utc)
    assert is_candle_closed(bars[1], Timeframe.H1, as_of) is True
    assert is_candle_closed(bars[2], Timeframe.H1, as_of) is False
    assert last_closed_index(bars, Timeframe.H1, as_of) == 1


def test_future_bars_do_not_shift_closed_index() -> None:
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    bars = [_bar(base + timedelta(hours=i)) for i in range(5)]
    as_of = base + timedelta(hours=2, minutes=30)  # closes 10,11,12? 12 open closes 13 — so 10 and 11 closed
    # bar0 open 10 close 11, bar1 open 11 close 12, bar2 open 12 close 13
    # as_of 12:30 → bar0, bar1 closed; bar2 not
    idx = last_closed_index(bars, Timeframe.H1, as_of)
    assert idx == 1
    # append mutated future
    bars2 = bars + [_bar(base + timedelta(hours=10))]
    assert last_closed_index(bars2, Timeframe.H1, as_of) == 1
