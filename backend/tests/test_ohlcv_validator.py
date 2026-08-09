"""Unit tests for OHLCV validation (Phase 1)."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.market.schemas import OHLCVBar, Timeframe
from app.market.validator import OHLCVValidator, clip_to_range


def _bar(ts: datetime, **overrides: float) -> OHLCVBar:
    base = {
        "timestamp": ts,
        "symbol": "XAUUSD",
        "timeframe": Timeframe.H1,
        "open": 2350.0,
        "high": 2355.0,
        "low": 2345.0,
        "close": 2352.0,
        "volume": 1000.0,
        "source": "test",
    }
    base.update(overrides)
    return OHLCVBar(**base)


def test_valid_series_passes() -> None:
    start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars = [_bar(start + timedelta(hours=i), close=2350 + i * 0.1, open=2350 + i * 0.1,
                 high=2351 + i * 0.1, low=2349 + i * 0.1) for i in range(5)]
    report = OHLCVValidator().validate(bars, expect_symbol="XAUUSD", expect_timeframe=Timeframe.H1)
    assert report.is_valid
    assert report.bar_count == 5
    assert report.missing_timestamps == []


def test_duplicate_timestamps_are_blocking() -> None:
    ts = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = [_bar(ts), _bar(ts, close=2351.0, high=2356.0)]
    report = OHLCVValidator().validate(bars, check_missing=False)
    assert not report.is_valid
    assert report.duplicate_timestamps
    assert any(i.code == "duplicate_timestamp" for i in report.issues)


def test_invalid_ohlc_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        _bar(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=2350,
            high=2340,  # invalid: high < open
            low=2330,
            close=2345,
        )


def test_chronological_order_detected() -> None:
    t0 = datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc)
    t1 = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    report = OHLCVValidator().validate([_bar(t0), _bar(t1)], check_missing=False)
    assert not report.is_valid
    assert any(i.code == "chronological_order" for i in report.issues)


def test_missing_candles_reported_not_filled() -> None:
    start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars = [_bar(start), _bar(start + timedelta(hours=2))]  # gap at +1h
    report = OHLCVValidator().validate(bars, expect_timeframe=Timeframe.H1)
    assert report.is_valid  # missing is warning, not blocking
    assert len(report.missing_timestamps) == 1
    assert report.missing_timestamps[0] == start + timedelta(hours=1)


def test_clip_to_range_excludes_outside_window() -> None:
    start = datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)
    bars = [_bar(start + timedelta(hours=i)) for i in range(5)]
    clipped = clip_to_range(bars, start + timedelta(hours=1), start + timedelta(hours=3))
    assert [b.timestamp for b in clipped] == [
        start + timedelta(hours=1),
        start + timedelta(hours=2),
        start + timedelta(hours=3),
    ]


def test_naive_timestamp_normalized_to_utc() -> None:
    bar = OHLCVBar(
        timestamp=datetime(2024, 1, 1, 12, 0),  # naive
        symbol="xauusd",
        timeframe=Timeframe.H1,
        open=1,
        high=2,
        low=0.5,
        close=1.5,
        volume=1,
    )
    assert bar.timestamp.tzinfo is not None
    assert bar.symbol == "XAUUSD"
