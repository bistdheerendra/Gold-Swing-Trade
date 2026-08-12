"""Unit tests for Phase 11.10 / 11.10.1 trading session tagging (DST-aware)."""

from datetime import datetime, timezone

import pytest

from app.core.sessions import (
    SessionId,
    dominant_session,
    sessions_for_timestamp,
    supports_session_bands,
    utc_windows_for_date,
)


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# --- Summer 2026-06-15: London BST (UTC+1), New York EDT (UTC-4) ---
# London local 08–17 → 07:00–16:00 UTC
# NY local 08–17 → 12:00–21:00 UTC
# Overlap → 12:00–16:00 UTC


@pytest.mark.parametrize(
    "ts,expected",
    [
        (_utc(2026, 6, 15, 0, 0), {SessionId.ASIA}),
        (_utc(2026, 6, 15, 7, 0), {SessionId.ASIA, SessionId.LONDON}),
        (_utc(2026, 6, 15, 8, 59), {SessionId.ASIA, SessionId.LONDON}),
        (_utc(2026, 6, 15, 9, 0), {SessionId.LONDON}),
        (_utc(2026, 6, 15, 6, 0), {SessionId.ASIA}),
        # NY opens 12:00 UTC in summer (1h earlier than old fixed 13:00 window)
        (
            _utc(2026, 6, 15, 12, 0),
            {
                SessionId.LONDON,
                SessionId.NEW_YORK,
                SessionId.LONDON_NY_OVERLAP,
            },
        ),
        (
            _utc(2026, 6, 15, 13, 0),
            {
                SessionId.LONDON,
                SessionId.NEW_YORK,
                SessionId.LONDON_NY_OVERLAP,
            },
        ),
        (
            _utc(2026, 6, 15, 15, 59),
            {
                SessionId.LONDON,
                SessionId.NEW_YORK,
                SessionId.LONDON_NY_OVERLAP,
            },
        ),
        (_utc(2026, 6, 15, 16, 0), {SessionId.NEW_YORK}),
        (_utc(2026, 6, 15, 20, 59), {SessionId.NEW_YORK}),
        (_utc(2026, 6, 15, 21, 0), set()),
    ],
)
def test_summer_dst_both_on(ts: datetime, expected: set[SessionId]) -> None:
    assert set(sessions_for_timestamp(ts)) == expected


# --- Winter 2026-01-15: London GMT (UTC+0), New York EST (UTC-5) ---
# London local 08–17 → 08:00–17:00 UTC
# NY local 08–17 → 13:00–22:00 UTC
# Overlap → 13:00–17:00 UTC


@pytest.mark.parametrize(
    "ts,expected",
    [
        (_utc(2026, 1, 15, 7, 0), {SessionId.ASIA}),  # London not open yet
        (_utc(2026, 1, 15, 8, 0), {SessionId.ASIA, SessionId.LONDON}),
        (
            _utc(2026, 1, 15, 12, 0),
            {SessionId.LONDON},
        ),  # NY still closed (opens 13:00)
        (
            _utc(2026, 1, 15, 13, 0),
            {
                SessionId.LONDON,
                SessionId.NEW_YORK,
                SessionId.LONDON_NY_OVERLAP,
            },
        ),
        (_utc(2026, 1, 15, 17, 0), {SessionId.NEW_YORK}),
        (_utc(2026, 1, 15, 21, 59), {SessionId.NEW_YORK}),
        (_utc(2026, 1, 15, 22, 0), set()),
    ],
)
def test_winter_dst_both_off(ts: datetime, expected: set[SessionId]) -> None:
    assert set(sessions_for_timestamp(ts)) == expected


def test_spring_transition_gap_us_on_uk_off() -> None:
    """2026-03-15: US already on EDT; UK still on GMT (EU switches Mar 29)."""
    # London 08–17 UTC, NY 12–21 UTC, overlap 12–17 UTC
    windows = utc_windows_for_date(_utc(2026, 3, 15, 12, 0))
    assert windows[SessionId.LONDON] == (8 * 60, 17 * 60)
    assert windows[SessionId.NEW_YORK] == (12 * 60, 21 * 60)
    assert windows[SessionId.LONDON_NY_OVERLAP] == (12 * 60, 17 * 60)

    # 12:00 UTC: London+NY+overlap (NY already open; would be closed under winter NY)
    assert set(sessions_for_timestamp(_utc(2026, 3, 15, 12, 0))) == {
        SessionId.LONDON,
        SessionId.NEW_YORK,
        SessionId.LONDON_NY_OVERLAP,
    }
    # 07:00 UTC: Asia only — London still on GMT so opens at 08:00
    assert set(sessions_for_timestamp(_utc(2026, 3, 15, 7, 0))) == {SessionId.ASIA}


def test_autumn_transition_gap_uk_off_us_on() -> None:
    """2025-10-28: UK back on GMT; US still on EDT (US ends Nov 2)."""
    windows = utc_windows_for_date(_utc(2025, 10, 28, 12, 0))
    assert windows[SessionId.LONDON] == (8 * 60, 17 * 60)
    assert windows[SessionId.NEW_YORK] == (12 * 60, 21 * 60)
    assert windows[SessionId.LONDON_NY_OVERLAP] == (12 * 60, 17 * 60)


def test_historical_candle_uses_own_date_not_today() -> None:
    """A winter candle must not inherit summer NY open (12:00)."""
    winter_noon = _utc(2026, 1, 15, 12, 0)
    summer_noon = _utc(2026, 6, 15, 12, 0)
    assert SessionId.NEW_YORK not in sessions_for_timestamp(winter_noon)
    assert SessionId.NEW_YORK in sessions_for_timestamp(summer_noon)


def test_dominant_prefers_overlap() -> None:
    ids = [
        SessionId.ASIA,
        SessionId.LONDON,
        SessionId.NEW_YORK,
        SessionId.LONDON_NY_OVERLAP,
    ]
    assert dominant_session(ids) == SessionId.LONDON_NY_OVERLAP


def test_session_bands_intraday_only() -> None:
    assert supports_session_bands("15m")
    assert supports_session_bands("30m")
    assert supports_session_bands("1h")
    assert not supports_session_bands("4h")
    assert not supports_session_bands("1d")


def test_summer_payload_ny_opens_earlier_than_old_fixed() -> None:
    """August/June: NY UTC window starts 12:00, not the old fixed 13:00."""
    windows = utc_windows_for_date(_utc(2026, 8, 12, 10, 0))
    assert windows[SessionId.NEW_YORK][0] == 12 * 60
    assert windows[SessionId.LONDON_NY_OVERLAP][0] == 12 * 60
    assert windows[SessionId.LONDON] == (7 * 60, 16 * 60)
