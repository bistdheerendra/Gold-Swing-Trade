"""Trading session windows for gold/PAXGUSD display overlays (Phase 11.10 / 11.10.1).

Asia uses a fixed UTC window (Japan has no DST). London and New York use
local-clock hours converted via zoneinfo (Europe/London, America/New_York) so
DST is correct for the candle's own date — including historical chart bars.

London+NY overlap is the intersection of the two DST-aware windows, not a
separate fixed constant.

Display / reference only — never feed into strategy, combined signal, or risk.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from enum import Enum
from typing import Iterable, List, Optional, Sequence, Tuple
from zoneinfo import ZoneInfo

from app.market.schemas import ensure_utc

# IST = UTC+5:30 (no DST) — used only for display labels
IST_OFFSET_MINUTES = 5 * 60 + 30

TZ_LONDON = ZoneInfo("Europe/London")
TZ_NEW_YORK = ZoneInfo("America/New_York")

# FX-style local session clocks (standard hours; DST shifts the UTC mapping)
LONDON_LOCAL_START = time(8, 0)
LONDON_LOCAL_END = time(17, 0)  # half-open [start, end)
NY_LOCAL_START = time(8, 0)
NY_LOCAL_END = time(17, 0)

# Asia / Tokyo-equivalent: fixed UTC (no DST in Japan). Matches prior Phase 11.10.
ASIA_UTC_START_MINUTE = 0
ASIA_UTC_END_MINUTE = 9 * 60


class SessionId(str, Enum):
    ASIA = "asia"
    LONDON = "london"
    NEW_YORK = "new_york"
    LONDON_NY_OVERLAP = "london_ny_overlap"


class WindowMode(str, Enum):
    FIXED_UTC = "fixed_utc"
    LOCAL = "local"
    OVERLAP = "overlap"


@dataclass(frozen=True)
class SessionMeta:
    """Static session identity + visuals (UTC windows are computed per-date)."""

    id: SessionId
    name: str
    behavior: str
    color: str
    emoji: str
    chart_fill: str
    priority: int
    window_mode: WindowMode
    timezone: Optional[str] = None
    local_start_minute: Optional[int] = None
    local_end_minute: Optional[int] = None
    # Asia only
    utc_start_minute: Optional[int] = None
    utc_end_minute: Optional[int] = None


SESSION_META: tuple[SessionMeta, ...] = (
    SessionMeta(
        id=SessionId.ASIA,
        name="Asia",
        behavior="Often range-bound / lower volatility",
        color="#3b82f6",
        emoji="🟦",
        chart_fill="rgba(59, 130, 246, 0.12)",
        priority=1,
        window_mode=WindowMode.FIXED_UTC,
        utc_start_minute=ASIA_UTC_START_MINUTE,
        utc_end_minute=ASIA_UTC_END_MINUTE,
    ),
    SessionMeta(
        id=SessionId.LONDON,
        name="London",
        behavior="Volatility increases",
        color="#eab308",
        emoji="🟨",
        chart_fill="rgba(234, 179, 8, 0.12)",
        priority=2,
        window_mode=WindowMode.LOCAL,
        timezone="Europe/London",
        local_start_minute=LONDON_LOCAL_START.hour * 60 + LONDON_LOCAL_START.minute,
        local_end_minute=LONDON_LOCAL_END.hour * 60 + LONDON_LOCAL_END.minute,
    ),
    SessionMeta(
        id=SessionId.NEW_YORK,
        name="New York",
        behavior="One of the highest-movement windows",
        color="#ef4444",
        emoji="🟥",
        chart_fill="rgba(239, 68, 68, 0.14)",
        priority=3,
        window_mode=WindowMode.LOCAL,
        timezone="America/New_York",
        local_start_minute=NY_LOCAL_START.hour * 60 + NY_LOCAL_START.minute,
        local_end_minute=NY_LOCAL_END.hour * 60 + NY_LOCAL_END.minute,
    ),
    SessionMeta(
        id=SessionId.LONDON_NY_OVERLAP,
        name="London + NY Overlap",
        behavior="Most significant window (highest volatility)",
        color="#f97316",
        emoji="🔥",
        chart_fill="rgba(249, 115, 22, 0.22)",
        priority=4,
        window_mode=WindowMode.OVERLAP,
    ),
)

_BY_ID: dict[SessionId, SessionMeta] = {s.id: s for s in SESSION_META}

# Back-compat alias used by older imports / docs wording
SESSION_DEFINITIONS = SESSION_META

# Intraday TFs where session bands are meaningful
SESSION_BAND_TIMEFRAMES: frozenset[str] = frozenset({"15m", "30m", "1h"})


def get_session_definition(session_id: SessionId | str) -> SessionMeta:
    key = SessionId(session_id) if not isinstance(session_id, SessionId) else session_id
    return _BY_ID[key]


def _minute_of_day(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


def _in_window(minute: int, start: int, end: int) -> bool:
    """Half-open [start, end) in minutes-from-midnight.

    Supports end > 1440 for wrap-around (minute in [start, 1440) U [0, end-1440)).
    """
    if end <= 1440:
        return start <= minute < end
    return minute >= start or minute < (end - 1440)


def _in_local_session(
    ts: datetime,
    tz: ZoneInfo,
    start_minute: int,
    end_minute: int,
) -> bool:
    local = ensure_utc(ts).astimezone(tz)
    return _in_window(_minute_of_day(local), start_minute, end_minute)


def _in_asia(ts: datetime) -> bool:
    utc = ensure_utc(ts)
    return _in_window(_minute_of_day(utc), ASIA_UTC_START_MINUTE, ASIA_UTC_END_MINUTE)


def _in_london(ts: datetime) -> bool:
    return _in_local_session(
        ts,
        TZ_LONDON,
        LONDON_LOCAL_START.hour * 60 + LONDON_LOCAL_START.minute,
        LONDON_LOCAL_END.hour * 60 + LONDON_LOCAL_END.minute,
    )


def _in_new_york(ts: datetime) -> bool:
    return _in_local_session(
        ts,
        TZ_NEW_YORK,
        NY_LOCAL_START.hour * 60 + NY_LOCAL_START.minute,
        NY_LOCAL_END.hour * 60 + NY_LOCAL_END.minute,
    )


def sessions_for_timestamp(ts: datetime) -> List[SessionId]:
    """Return all sessions containing ``ts``.

    Uses the DST rules in effect on that instant's calendar date in each region
    (via zoneinfo) — not today's DST state.
    """
    matched: List[SessionId] = []
    if _in_asia(ts):
        matched.append(SessionId.ASIA)
    london = _in_london(ts)
    ny = _in_new_york(ts)
    if london:
        matched.append(SessionId.LONDON)
    if ny:
        matched.append(SessionId.NEW_YORK)
    if london and ny:
        matched.append(SessionId.LONDON_NY_OVERLAP)
    return matched


def sessions_for_timestamps(timestamps: Iterable[datetime]) -> List[List[SessionId]]:
    return [sessions_for_timestamp(ts) for ts in timestamps]


def dominant_session(session_ids: Sequence[SessionId]) -> Optional[SessionId]:
    """Highest-priority session for a single chart-band color (overlap wins)."""
    if not session_ids:
        return None
    return max(session_ids, key=lambda sid: _BY_ID[sid].priority)


def active_sessions_now(now: Optional[datetime] = None) -> List[SessionId]:
    return sessions_for_timestamp(now or datetime.now(timezone.utc))


def local_session_utc_window(
    as_of: datetime,
    tz: ZoneInfo,
    local_start: time,
    local_end: time,
) -> Tuple[int, int]:
    """Map local [start, end) on ``as_of``'s local calendar day → UTC minute-of-day."""
    local_date = ensure_utc(as_of).astimezone(tz).date()
    start_local = datetime.combine(local_date, local_start, tzinfo=tz)
    end_local = datetime.combine(local_date, local_end, tzinfo=tz)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    start_m = _minute_of_day(start_utc)
    end_m = _minute_of_day(end_utc)
    if end_m <= start_m:
        end_m += 24 * 60  # wrap past UTC midnight
    return start_m, end_m


def utc_windows_for_date(as_of: datetime) -> dict[SessionId, Tuple[int, int]]:
    """DST-aware UTC minute windows for the calendar day of ``as_of``."""
    london = local_session_utc_window(
        as_of, TZ_LONDON, LONDON_LOCAL_START, LONDON_LOCAL_END
    )
    ny = local_session_utc_window(as_of, TZ_NEW_YORK, NY_LOCAL_START, NY_LOCAL_END)
    overlap_start = max(london[0], ny[0])
    overlap_end = min(london[1], ny[1])
    windows = {
        SessionId.ASIA: (ASIA_UTC_START_MINUTE, ASIA_UTC_END_MINUTE),
        SessionId.LONDON: london,
        SessionId.NEW_YORK: ny,
    }
    if overlap_start < overlap_end:
        windows[SessionId.LONDON_NY_OVERLAP] = (overlap_start, overlap_end)
    else:
        # Degenerate (should not happen for 08–17 London ∩ NY); empty marker
        windows[SessionId.LONDON_NY_OVERLAP] = (overlap_start, overlap_start)
    return windows


def _format_clock(minute: int, *, hour12: bool = True) -> str:
    minute = minute % (24 * 60)
    h, m = divmod(minute, 60)
    if not hour12:
        return f"{h:02d}:{m:02d}"
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12
    if h12 == 0:
        h12 = 12
    if m == 0:
        return f"{h12}:00 {suffix}"
    return f"{h12}:{m:02d} {suffix}"


def _format_ist_window(utc_start: int, utc_end: int) -> str:
    ist_start = utc_start + IST_OFFSET_MINUTES
    ist_end = utc_end + IST_OFFSET_MINUTES
    return f"{_format_clock(ist_start)} – {_format_clock(ist_end)}"


def _format_utc_window(start_minute: int, end_minute: int) -> str:
    return (
        f"{_format_clock(start_minute, hour12=False)}–"
        f"{_format_clock(end_minute, hour12=False)} UTC"
    )


def session_definitions_payload(as_of: Optional[datetime] = None) -> List[dict]:
    """JSON-serializable definitions for the reference API / frontend.

    ``utc_*`` / ``ist_window`` reflect DST state for ``as_of`` (default: now).
    Local-mode sessions also expose timezone + local minutes so the chart can
    tag historical candles correctly without today's UTC window alone.
    """
    instant = ensure_utc(as_of) if as_of is not None else datetime.now(timezone.utc)
    windows = utc_windows_for_date(instant)
    rows: List[dict] = []
    for meta in SESSION_META:
        utc_start, utc_end = windows[meta.id]
        row: dict = {
            "id": meta.id.value,
            "name": meta.name,
            "ist_window": _format_ist_window(utc_start, utc_end),
            "utc_start_minute": utc_start,
            "utc_end_minute": utc_end,
            "utc_window": _format_utc_window(utc_start, utc_end),
            "behavior": meta.behavior,
            "color": meta.color,
            "emoji": meta.emoji,
            "chart_fill": meta.chart_fill,
            "priority": meta.priority,
            "window_mode": meta.window_mode.value,
            "timezone": meta.timezone,
            "local_start_minute": meta.local_start_minute,
            "local_end_minute": meta.local_end_minute,
        }
        rows.append(row)
    return rows


def supports_session_bands(timeframe: str) -> bool:
    return timeframe.strip().lower() in SESSION_BAND_TIMEFRAMES
