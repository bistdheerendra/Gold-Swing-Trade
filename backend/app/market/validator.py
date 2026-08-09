"""OHLCV validation — no look-ahead; reports gaps without fabricating prices."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Sequence

from app.market.schemas import (
    OHLCVBar,
    Timeframe,
    ValidationIssue,
    ValidationReport,
    ensure_utc,
    sort_bars,
)


class OHLCVValidator:
    """
    Validates normalized OHLCV series.

    Missing candles are reported, never filled with invented OHLC values.
    That keeps downstream feature/label pipelines free of fabricated history.
    """

    def validate(
        self,
        bars: Sequence[OHLCVBar],
        *,
        expect_symbol: str | None = None,
        expect_timeframe: Timeframe | None = None,
        check_missing: bool = True,
    ) -> ValidationReport:
        issues: List[ValidationIssue] = []
        missing: List[datetime] = []
        duplicates: List[datetime] = []

        if not bars:
            issues.append(
                ValidationIssue(code="empty", message="No bars provided")
            )
            return ValidationReport(
                is_valid=False,
                bar_count=0,
                issues=issues,
            )

        ordered = sort_bars(bars)

        # Timezone + symbol/timeframe consistency
        for bar in ordered:
            if bar.timestamp.tzinfo is None:
                issues.append(
                    ValidationIssue(
                        code="timezone",
                        message="Timestamp missing timezone (must be UTC)",
                        timestamp=bar.timestamp,
                    )
                )
            elif bar.timestamp.utcoffset() != timezone.utc.utcoffset(None):
                # Non-UTC offsets should already be normalized by schema; still guard.
                if ensure_utc(bar.timestamp) != bar.timestamp:
                    issues.append(
                        ValidationIssue(
                            code="timezone",
                            message="Timestamp is not UTC-normalized",
                            timestamp=bar.timestamp,
                        )
                    )

            if expect_symbol and bar.symbol != expect_symbol.upper():
                issues.append(
                    ValidationIssue(
                        code="symbol_mismatch",
                        message=f"Expected symbol {expect_symbol}, got {bar.symbol}",
                        timestamp=bar.timestamp,
                    )
                )
            if expect_timeframe and bar.timeframe != expect_timeframe:
                issues.append(
                    ValidationIssue(
                        code="timeframe_mismatch",
                        message=(
                            f"Expected timeframe {expect_timeframe.value}, "
                            f"got {bar.timeframe.value}"
                        ),
                        timestamp=bar.timestamp,
                    )
                )

            # Explicit OHLC invariant (schema also enforces; catch dict-built bars)
            try:
                OHLCVBar.model_validate(bar.model_dump())
            except Exception as exc:  # noqa: BLE001 — collect as validation issue
                issues.append(
                    ValidationIssue(
                        code="invalid_ohlc",
                        message=str(exc),
                        timestamp=bar.timestamp,
                    )
                )

        # Chronological order on original sequence
        for prev, curr in zip(bars, bars[1:]):
            if ensure_utc(curr.timestamp) < ensure_utc(prev.timestamp):
                issues.append(
                    ValidationIssue(
                        code="chronological_order",
                        message="Bars are not in chronological order",
                        timestamp=curr.timestamp,
                    )
                )
                break

        # Duplicates
        seen: set[datetime] = set()
        for bar in ordered:
            ts = ensure_utc(bar.timestamp)
            if ts in seen:
                duplicates.append(ts)
                issues.append(
                    ValidationIssue(
                        code="duplicate_timestamp",
                        message=f"Duplicate timestamp {ts.isoformat()}",
                        timestamp=ts,
                    )
                )
            seen.add(ts)

        # Missing candles relative to timeframe grid (within observed span only)
        if check_missing and len(ordered) >= 2:
            timeframe = ordered[0].timeframe
            step = timeframe.delta
            cursor = ensure_utc(ordered[0].timestamp)
            end = ensure_utc(ordered[-1].timestamp)
            present = {ensure_utc(bar.timestamp) for bar in ordered}
            # Bound iterations to avoid runaway on bad deltas
            max_steps = len(ordered) * 5 + 10
            steps = 0
            while cursor <= end and steps < max_steps:
                if cursor not in present:
                    missing.append(cursor)
                    issues.append(
                        ValidationIssue(
                            code="missing_candle",
                            message=f"Missing candle at {cursor.isoformat()}",
                            timestamp=cursor,
                        )
                    )
                cursor = cursor + step
                steps += 1

        blocking = {
            "duplicate_timestamp",
            "invalid_ohlc",
            "timezone",
            "chronological_order",
            "empty",
            "symbol_mismatch",
            "timeframe_mismatch",
        }
        is_valid = not any(issue.code in blocking for issue in issues)

        return ValidationReport(
            is_valid=is_valid,
            bar_count=len(bars),
            issues=issues,
            missing_timestamps=missing,
            duplicate_timestamps=duplicates,
        )


def clip_to_range(
    bars: Iterable[OHLCVBar],
    start: datetime | None,
    end: datetime | None,
    *,
    sort: bool = True,
) -> List[OHLCVBar]:
    """Inclusive clip — never returns bars outside the requested window."""
    start_utc = ensure_utc(start) if start else None
    end_utc = ensure_utc(end) if end else None
    result: List[OHLCVBar] = []
    for bar in bars:
        ts = ensure_utc(bar.timestamp)
        if start_utc and ts < start_utc:
            continue
        if end_utc and ts > end_utc:
            continue
        result.append(bar)
    return sort_bars(result) if sort else result
