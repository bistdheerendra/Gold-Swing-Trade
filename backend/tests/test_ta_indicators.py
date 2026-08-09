"""Tests for causal indicators (Phase 3)."""

from __future__ import annotations

import math

from app.ta.indicators import adx, atr, bollinger_bands, ema, macd, rsi, sma


def test_ema_warmup_and_recursion() -> None:
    closes = [1.0, 2.0, 3.0, 4.0, 5.0]
    values = ema(closes, 3)
    assert values[0] is None and values[1] is None
    assert values[2] == 2.0
    alpha = 2 / 4
    expected = alpha * 4 + (1 - alpha) * 2
    assert math.isclose(values[3], expected, rel_tol=1e-12)


def test_ema_causal_extension_stable() -> None:
    base = [10, 11, 12, 13, 14, 15, 16, 17]
    a = ema(base, 4)
    b = ema(base + [18, 19], 4)
    for i in range(len(base)):
        if a[i] is None:
            assert b[i] is None
        else:
            assert math.isclose(a[i], b[i], rel_tol=1e-12)


def test_rsi_bounds_and_warmup() -> None:
    closes = [i for i in range(1, 40)]
    values = rsi(closes, 14)
    assert all(v is None for v in values[:14])
    assert values[14] is not None
    for v in values:
        if v is not None:
            assert 0.0 <= v <= 100.0


def test_macd_lengths_align() -> None:
    closes = [100 + (i % 7) * 0.5 for i in range(80)]
    pack = macd(closes)
    assert len(pack["macd"]) == len(closes)
    assert len(pack["signal"]) == len(closes)
    assert len(pack["histogram"]) == len(closes)


def test_atr_positive_after_warmup() -> None:
    highs = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24]
    lows = [9, 10, 10.5, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]
    closes = [9.5, 10.5, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
    values = atr(highs, lows, closes, 5)
    assert values[4] is not None
    assert values[4] > 0


def test_bollinger_mid_is_sma() -> None:
    closes = list(range(1, 31))
    bb = bollinger_bands(closes, period=5, std_mult=2)
    s = sma(closes, 5)
    for i, (mid, sma_v) in enumerate(zip(bb["mid"], s)):
        if mid is None:
            assert sma_v is None
        else:
            assert math.isclose(mid, sma_v, rel_tol=1e-12)
            assert bb["upper"][i] is not None and bb["upper"][i] >= mid
            assert bb["lower"][i] is not None and bb["lower"][i] <= mid


def test_adx_warm_and_bounded() -> None:
    n = 60
    highs = [100 + i * 0.3 + (i % 3) for i in range(n)]
    lows = [99 + i * 0.3 - (i % 2) for i in range(n)]
    closes = [99.5 + i * 0.3 for i in range(n)]
    pack = adx(highs, lows, closes, 14)
    assert any(v is not None for v in pack["adx"])
    for key in ("adx", "plus_di", "minus_di"):
        for v in pack[key]:
            if v is not None:
                assert 0.0 <= v <= 100.0


def test_ema_manual_step_no_future() -> None:
    closes = [100.0, 101.0, 102.0, 103.0]
    values = ema(closes, 2)
    # index 2 must use only closes[2] and ema[1], not closes[3]
    alpha = 2 / 3
    expected = alpha * 102.0 + (1 - alpha) * values[1]
    assert math.isclose(values[2], expected, rel_tol=1e-12)
