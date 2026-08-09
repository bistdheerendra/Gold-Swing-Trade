"""MultiTimeframeAnalyzer tests (Phase 5)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.market.provider import MockMarketDataProvider
from app.market.schemas import Timeframe
from app.mtf.analyzer import MultiTimeframeAnalyzer
from app.mtf.schemas import BiasLabel, MtfState
import pytest


@pytest.mark.asyncio
async def test_mtf_analyze_produces_all_roles() -> None:
    provider = MockMarketDataProvider()
    end = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
    bars_by_tf = {}
    for tf in Timeframe:
        start = end - tf.delta * 400
        bars_by_tf[tf.value] = await provider.get_historical_ohlcv(
            "XAUUSD", tf, start, end
        )
    # as_of at end — all generated bars with open<=end may include unfinished if open==end
    as_of = end + timedelta(minutes=15)
    result = MultiTimeframeAnalyzer().analyze(
        bars_by_tf, symbol="XAUUSD", as_of=as_of
    )
    assert set(result.timeframes.keys()) >= {"1d", "4h", "1h", "30m", "15m"}
    assert result.macro.timeframe == "1d"
    assert result.setup.timeframe == "1h"
    assert result.timing.timeframe == "30m"
    assert result.entry.timeframe == "15m"
    assert -100 <= result.timeframes["1h"].bias_score <= 100
    assert 0 <= result.alignment_score <= 100
    assert result.state in set(MtfState)
    assert result.higher_timeframe_bias in set(BiasLabel)


@pytest.mark.asyncio
async def test_mtf_leakage_future_mutation() -> None:
    provider = MockMarketDataProvider()
    end = datetime(2024, 3, 1, 0, 0, tzinfo=timezone.utc)
    bars_by_tf = {}
    for tf in Timeframe:
        start = end - tf.delta * 350
        bars_by_tf[tf.value] = await provider.get_historical_ohlcv(
            "XAUUSD", tf, start, end + tf.delta * 20
        )
    as_of = end
    analyzer = MultiTimeframeAnalyzer()
    a = analyzer.analyze(bars_by_tf, symbol="XAUUSD", as_of=as_of)
    # Mutate only bars that open after as_of
    mutated = {}
    for tf, bars in bars_by_tf.items():
        new_bars = []
        for b in bars:
            if b.timestamp > as_of:
                new_bars.append(
                    b.model_copy(update={"high": b.high + 100, "close": b.close + 80})
                )
            else:
                new_bars.append(b)
        mutated[tf] = new_bars
    b = analyzer.analyze(mutated, symbol="XAUUSD", as_of=as_of)
    assert a.higher_timeframe_bias == b.higher_timeframe_bias
    assert a.setup_bias == b.setup_bias
    assert a.entry_bias == b.entry_bias
    for tf in ("1d", "4h", "1h", "30m", "15m"):
        assert a.timeframes[tf].bias_score == b.timeframes[tf].bias_score
