"""TechnicalAnalysisEngine tests (Phase 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.market.schemas import OHLCVBar, Timeframe
from app.ta.engine import TechnicalAnalysisEngine


def _bars(n: int = 120) -> list[OHLCVBar]:
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    out: list[OHLCVBar] = []
    price = 2300.0
    for i in range(n):
        o = price
        c = price + ((i % 5) - 2) * 0.4
        h = max(o, c) + 1.2
        l = min(o, c) - 1.2
        out.append(
            OHLCVBar(
                timestamp=start + timedelta(hours=i),
                symbol="XAUUSD",
                timeframe=Timeframe.H1,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=1000 + i,
                source="test",
            )
        )
        price = c
    return out


def test_engine_analyze_latest_fields() -> None:
    engine = TechnicalAnalysisEngine()
    result = engine.analyze(_bars(), symbol="XAUUSD", timeframe="1h")
    assert result.bar_count == 120
    assert result.latest.ema_20 is not None
    assert result.latest.rsi is not None
    assert result.latest.atr is not None
    assert "ema_20" in result.series
    assert len(result.series["ema_20"]) == 120


def test_engine_as_of_truncation_no_look_ahead() -> None:
    bars = _bars(100)
    engine = TechnicalAnalysisEngine()
    early = engine.analyze(bars, symbol="XAUUSD", timeframe="1h", as_of_index=60)
    # Recompute with only first 61 bars must match
    truncated = engine.analyze(bars[:61], symbol="XAUUSD", timeframe="1h")
    assert early.latest.rsi == truncated.latest.rsi
    assert early.latest.ema_20 == truncated.latest.ema_20
    assert early.series["macd"] == truncated.series["macd"]
    assert early.bar_count == 61


def test_engine_rejects_empty() -> None:
    with pytest.raises(ValueError):
        TechnicalAnalysisEngine().analyze([], symbol="XAUUSD", timeframe="1h")
