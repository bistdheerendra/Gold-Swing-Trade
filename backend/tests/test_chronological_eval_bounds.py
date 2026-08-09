"""Phase 11.6 — chronological eval bounds keep warmup context for TEST."""

from app.backtest.validation import chronological_eval_bounds, chronological_slice
from app.market.schemas import OHLCVBar, Timeframe
from datetime import datetime, timedelta, timezone


def _bars(n: int):
    start = datetime(2026, 3, 1, tzinfo=timezone.utc)
    out = []
    for i in range(n):
        ts = start + timedelta(minutes=15 * i)
        out.append(
            OHLCVBar(
                timestamp=ts,
                symbol="PAXGUSD",
                timeframe=Timeframe.M15,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.5,
                volume=1.0,
                source="test",
            )
        )
    return out


def test_eval_bounds_partition() -> None:
    n = 1000
    t0, t1, _ = chronological_eval_bounds(n, segment="TRAIN")
    v0, v1, _ = chronological_eval_bounds(n, segment="VALIDATION")
    s0, s1, _ = chronological_eval_bounds(n, segment="TEST")
    assert t0 == 0
    assert t1 == v0
    assert v1 == s0
    assert s1 == n
    assert t1 > 0 and (v1 - v0) > 0 and (s1 - s0) > 0


def test_test_slice_shorter_than_warmup_but_bounds_ok() -> None:
    """Classic failure mode: TEST ~15% of 400 = 60 bars < warmup 80."""
    n = 400
    s0, s1, name = chronological_eval_bounds(n, segment="TEST")
    assert name == "TEST"
    assert (s1 - s0) < 80
    # Full series still has warmup room before TEST
    assert s0 >= 80


def test_chronological_slice_still_works() -> None:
    bars = _bars(200)
    test, name = chronological_slice(bars, segment="TEST")
    assert name == "TEST"
    assert len(test) > 0
    assert test[0].timestamp >= bars[0].timestamp
