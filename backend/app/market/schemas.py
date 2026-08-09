"""Normalized market data schemas and timeframe helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Timeframe(str, Enum):
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"

    @property
    def delta(self) -> timedelta:
        mapping = {
            Timeframe.M15: timedelta(minutes=15),
            Timeframe.M30: timedelta(minutes=30),
            Timeframe.H1: timedelta(hours=1),
            Timeframe.H4: timedelta(hours=4),
            Timeframe.D1: timedelta(days=1),
        }
        return mapping[self]


SUPPORTED_TIMEFRAMES: tuple[Timeframe, ...] = tuple(Timeframe)

# Single source of truth for MTF hierarchy (macro → entry)
# 1D → 4H → 1H → 30M → 15M
MTF_HIERARCHY: tuple[str, ...] = ("1d", "4h", "1h", "30m", "15m")
ANALYSIS_TIMEFRAMES: tuple[str, ...] = MTF_HIERARCHY



def parse_timeframe(value: str) -> Timeframe:
    try:
        return Timeframe(value)
    except ValueError as exc:
        allowed = ", ".join(tf.value for tf in Timeframe)
        raise ValueError(f"Unsupported timeframe '{value}'. Allowed: {allowed}") from exc


def ensure_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


class OHLCVBar(BaseModel):
    """Canonical OHLCV candle used across the platform."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    symbol: str
    timeframe: Timeframe
    open: float
    high: float
    low: float
    close: float
    volume: float = Field(ge=0)
    source: str = "unknown"

    @field_validator("timestamp")
    @classmethod
    def _utc_timestamp(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol must be non-empty")
        return normalized

    @model_validator(mode="after")
    def _validate_ohlc(self) -> "OHLCVBar":
        if self.high < max(self.open, self.close):
            raise ValueError("high must be >= max(open, close)")
        if self.low > min(self.open, self.close):
            raise ValueError("low must be <= min(open, close)")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        return self


class ValidationIssue(BaseModel):
    code: str
    message: str
    timestamp: Optional[datetime] = None


class ValidationReport(BaseModel):
    is_valid: bool
    bar_count: int
    issues: List[ValidationIssue] = Field(default_factory=list)
    missing_timestamps: List[datetime] = Field(default_factory=list)
    duplicate_timestamps: List[datetime] = Field(default_factory=list)

    @property
    def has_blocking_errors(self) -> bool:
        blocking = {
            "duplicate_timestamp",
            "invalid_ohlc",
            "timezone",
            "chronological_order",
            "empty",
        }
        return any(issue.code in blocking for issue in self.issues)


class OHLCVQuery(BaseModel):
    symbol: str
    timeframe: Timeframe
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    limit: Optional[int] = Field(default=None, gt=0, le=50_000)

    @field_validator("symbol")
    @classmethod
    def _symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("start", "end")
    @classmethod
    def _utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        return ensure_utc(value) if value is not None else None


def sort_bars(bars: Iterable[OHLCVBar]) -> List[OHLCVBar]:
    return sorted(bars, key=lambda bar: bar.timestamp)
