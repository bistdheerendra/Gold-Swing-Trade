"""SMC detector unit tests (Phase 4)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.market.schemas import OHLCVBar, Timeframe
from app.smc.engine import SmcEngine
from app.smc.fvg import detect_fvgs
from app.smc.schemas import FvgLifecycle, SmcConfig, SmcDirection, SmcEventType
from app.smc.structure_breaks import detect_bos_choch
from app.ta.structure import detect_swings


def _bar(i: int, o: float, h: float, l: float, c: float) -> OHLCVBar:
    return OHLCVBar(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i),
        symbol="XAUUSD",
        timeframe=Timeframe.H1,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=1000,
        source="test",
    )


def _series_from_tuples(rows: list[tuple[float, float, float, float]]) -> list[OHLCVBar]:
    return [_bar(i, *row) for i, row in enumerate(rows)]


def test_bullish_fvg_and_fill() -> None:
    # i-2 high=10, i low=12 → bullish gap 10..12 at index 2
    highs = [10, 11, 13, 13, 9]
    lows = [8, 9, 12, 11, 8]
    fvgs = detect_fvgs(highs, lows, timeframe="1h", config=SmcConfig(), as_of_index=2)
    assert len(fvgs) == 1
    assert fvgs[0].type == SmcEventType.BULLISH_FVG
    assert fvgs[0].confirm_index == 2
    filled = detect_fvgs(highs, lows, timeframe="1h", config=SmcConfig(), as_of_index=4)
    assert filled[0].lifecycle == FvgLifecycle.FILLED
    assert filled[0].fill_index == 4


def test_bearish_fvg() -> None:
    highs = [12, 11, 9]
    lows = [10, 9, 7]
    # high[2]=9 < low[0]=10 → bearish FVG
    fvgs = detect_fvgs(highs, lows, timeframe="1h", config=SmcConfig(), as_of_index=2)
    assert any(f.type == SmcEventType.BEARISH_FVG for f in fvgs)


def test_bos_close_vs_wick() -> None:
    # Build swings then break
    # Create clear swing high at index 4 price 20, confirm at 6
    highs = [10, 11, 12, 13, 20, 12, 11, 10, 10, 10, 21, 21]
    lows = [9, 10, 11, 12, 12, 10, 9, 8, 8, 8, 15, 15]
    closes_fail = [9.5, 10.5, 11.5, 12.5, 15, 11, 10, 9, 9, 9, 19.5, 19.5]  # wick would break but close below
    closes_ok = [9.5, 10.5, 11.5, 12.5, 15, 11, 10, 9, 9, 9, 21.5, 21.5]
    swings = detect_swings(highs, lows, left=2, right=2, as_of_index=11)
    cfg_close = SmcConfig(break_on_close=True, break_on_wick=False)
    bos_fail, _, _ = detect_bos_choch(
        highs, lows, closes_fail, swings, timeframe="1h", config=cfg_close, as_of_index=11
    )
    # high goes to 21 but close 19.5 < 20 → no bullish BOS on close rule
    assert not any(b.broken_level == 20 and b.direction == SmcDirection.BULLISH for b in bos_fail)

    bos_ok, _, _ = detect_bos_choch(
        highs, lows, closes_ok, swings, timeframe="1h", config=cfg_close, as_of_index=11
    )
    assert any(b.direction == SmcDirection.BULLISH and b.broken_level == 20 for b in bos_ok)

    cfg_wick = SmcConfig(break_on_close=False, break_on_wick=True)
    bos_wick, _, _ = detect_bos_choch(
        highs, lows, closes_fail, swings, timeframe="1h", config=cfg_wick, as_of_index=11
    )
    assert any(b.direction == SmcDirection.BULLISH for b in bos_wick)


def test_engine_dealing_range_zones() -> None:
    # Synthetic trending bars
    rows = []
    price = 2000.0
    for i in range(80):
        o = price
        c = price + (1.5 if i % 7 != 0 else -2.0)
        h = max(o, c) + 3
        l = min(o, c) - 3
        rows.append((o, h, l, c))
        price = c
    bars = _series_from_tuples(rows)
    result = SmcEngine().analyze(bars, symbol="XAUUSD", timeframe="1h")
    assert result.dealing_range.zone.value in {"PREMIUM", "DISCOUNT", "EQUILIBRIUM", "UNKNOWN"}
    assert 0 <= result.smc_score <= 100
    assert "structure" in result.summary


def test_future_mutation_does_not_change_past_smc() -> None:
    rows = []
    price = 2300.0
    for i in range(60):
        o = price
        c = price + ((i % 5) - 2) * 0.8
        h = max(o, c) + 2
        l = min(o, c) - 2
        rows.append((o, h, l, c))
        price = c
    bars = _series_from_tuples(rows)
    engine = SmcEngine()
    early = engine.analyze(bars, symbol="XAUUSD", timeframe="1h", as_of_index=40)
    # Mutate future bars only
    mutated = list(bars)
    for i in range(41, 60):
        b = mutated[i]
        mutated[i] = b.model_copy(
            update={"high": b.high + 50, "low": b.low - 50, "close": b.close + 40}
        )
    later_view = engine.analyze(mutated, symbol="XAUUSD", timeframe="1h", as_of_index=40)
    assert [e.id for e in early.bos] == [e.id for e in later_view.bos]
    assert [e.id for e in early.choch] == [e.id for e in later_view.choch]
    assert [e.id for e in early.fvg] == [e.id for e in later_view.fvg]
    assert early.dealing_range.equilibrium == later_view.dealing_range.equilibrium


def test_fvg_not_available_before_creation_candle() -> None:
    highs = [10, 11, 13]
    lows = [8, 9, 12]
    assert detect_fvgs(highs, lows, timeframe="1h", config=SmcConfig(), as_of_index=1) == []
    assert len(detect_fvgs(highs, lows, timeframe="1h", config=SmcConfig(), as_of_index=2)) == 1
