"""Historical data quality checks — report errors; do not silently repair."""

from __future__ import annotations

from datetime import datetime
from typing import List, Sequence, Tuple

from app.market.schemas import OHLCVBar, ensure_utc


class DataQualityReport:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_ohlcv_series(
    bars: Sequence[OHLCVBar],
    *,
    symbol: str,
    min_bars: int = 50,
) -> DataQualityReport:
    report = DataQualityReport()
    if len(bars) < min_bars:
        report.errors.append(f"Insufficient bars: {len(bars)} < {min_bars}")
        return report

    prev_ts: datetime | None = None
    seen: set[datetime] = set()
    for i, b in enumerate(bars):
        ts = ensure_utc(b.timestamp)
        if b.symbol.upper() != symbol.upper():
            report.errors.append(f"Bar {i}: symbol mismatch {b.symbol} != {symbol}")
        if b.open <= 0 or b.high <= 0 or b.low <= 0 or b.close <= 0:
            report.errors.append(f"Bar {i} @ {ts.isoformat()}: non-positive OHLC")
        if b.high < b.low:
            report.errors.append(f"Bar {i}: high < low")
        if b.high < max(b.open, b.close) or b.low > min(b.open, b.close):
            report.errors.append(f"Bar {i}: invalid OHLC envelope")
        if abs(b.high - b.low) == 0 and b.open != b.close:
            report.warnings.append(f"Bar {i}: zero range with open!=close")
        if ts in seen:
            report.errors.append(f"Duplicate timestamp: {ts.isoformat()}")
        seen.add(ts)
        if prev_ts is not None and ts < prev_ts:
            report.errors.append(
                f"Timestamps not sorted at {i}: {ts.isoformat()} < {prev_ts.isoformat()}"
            )
        if prev_ts is not None and ts == prev_ts:
            report.errors.append(f"Duplicate adjacent timestamp at {i}")
        if b.timestamp.tzinfo is None:
            report.warnings.append(f"Bar {i}: naive timestamp coerced to UTC expected")
        prev_ts = ts

    # Gap warnings (non-blocking) — Gold sessions vary; do not hard-fail
    if len(bars) >= 2:
        deltas = [
            (ensure_utc(bars[i].timestamp) - ensure_utc(bars[i - 1].timestamp)).total_seconds()
            for i in range(1, min(len(bars), 200))
        ]
        if deltas:
            median = sorted(deltas)[len(deltas) // 2]
            if median > 0:
                gaps = 0
                for i in range(1, len(bars)):
                    d = (
                        ensure_utc(bars[i].timestamp) - ensure_utc(bars[i - 1].timestamp)
                    ).total_seconds()
                    if d > median * 3.5:
                        gaps += 1
                if gaps:
                    report.warnings.append(
                        f"Detected {gaps} potential missing-candle gaps (non-blocking; Gold sessions vary)"
                    )
    return report


def chronological_slice(
    bars: Sequence[OHLCVBar],
    *,
    segment: str,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> Tuple[List[OHLCVBar], str]:
    """
    Return chronological TRAIN / VALIDATION / TEST / ALL slice.
    Never shuffles.

    Note: For backtest evaluation prefer chronological_eval_bounds + full-series
    context so warmup is not applied to an isolated short TEST slice.
    """
    n = len(bars)
    seg = (segment or "ALL").upper()
    if seg == "ALL":
        return list(bars), "ALL"
    start, end, name = chronological_eval_bounds(
        n,
        segment=seg,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        test_ratio=test_ratio,
    )
    return list(bars[start:end]), name


def chronological_eval_bounds(
    n: int,
    *,
    segment: str,
    train_ratio: float = 0.70,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
) -> Tuple[int, int, str]:
    """
    Chronological index bounds [start, end) for an evaluation segment.

    TRAIN / VALIDATION / TEST share the same cut points on the full series.
    Callers should keep the full bar series for causal context/warmup and only
    *evaluate* signals inside these bounds (Phase 11.6 measurement fix).
    """
    seg = (segment or "ALL").upper()
    if seg == "ALL":
        return 0, n, "ALL"
    if n <= 0:
        return 0, 0, seg
    t_end = int(n * train_ratio)
    v_end = int(n * (train_ratio + validation_ratio))
    t_end = max(1, min(t_end, n - 2)) if n > 2 else n
    v_end = max(t_end + 1, min(v_end, n - 1)) if n > 2 else n
    if seg == "TRAIN":
        return 0, t_end, "TRAIN"
    if seg in ("VALIDATION", "VAL"):
        return t_end, v_end, "VALIDATION"
    if seg == "TEST":
        return v_end, n, "TEST"
    raise ValueError(f"Unknown split segment: {segment}")
