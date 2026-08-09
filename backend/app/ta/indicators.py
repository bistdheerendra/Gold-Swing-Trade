"""Causal technical indicators (no look-ahead)."""

from __future__ import annotations

from typing import List, Optional, Sequence

import numpy as np


def _as_float_array(values: Sequence[float]) -> np.ndarray:
    return np.asarray(values, dtype=np.float64)


def ema(values: Sequence[float], period: int) -> List[Optional[float]]:
    """
    Exponential moving average.
    Warm-up: SMA of first `period` samples at index period-1, then recursive EMA.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    arr = _as_float_array(values)
    n = len(arr)
    out: List[Optional[float]] = [None] * n
    if n < period:
        return out

    seed = float(np.mean(arr[:period]))
    out[period - 1] = seed
    alpha = 2.0 / (period + 1)
    prev = seed
    for i in range(period, n):
        prev = alpha * float(arr[i]) + (1.0 - alpha) * prev
        out[i] = prev
    return out


def sma(values: Sequence[float], period: int) -> List[Optional[float]]:
    if period < 1:
        raise ValueError("period must be >= 1")
    arr = _as_float_array(values)
    n = len(arr)
    out: List[Optional[float]] = [None] * n
    if n < period:
        return out
    window_sum = float(np.sum(arr[:period]))
    out[period - 1] = window_sum / period
    for i in range(period, n):
        window_sum += float(arr[i]) - float(arr[i - period])
        out[i] = window_sum / period
    return out


def rsi(closes: Sequence[float], period: int = 14) -> List[Optional[float]]:
    """Wilder RSI — uses only past deltas through index i."""
    if period < 1:
        raise ValueError("period must be >= 1")
    arr = _as_float_array(closes)
    n = len(arr)
    out: List[Optional[float]] = [None] * n
    if n <= period:
        return out

    deltas = np.diff(arr)
    gains = np.clip(deltas, 0.0, None)
    losses = np.clip(-deltas, 0.0, None)

    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))
    out[period] = _rsi_from_avgs(avg_gain, avg_loss)

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + float(gains[i])) / period
        avg_loss = (avg_loss * (period - 1) + float(losses[i])) / period
        out[i + 1] = _rsi_from_avgs(avg_gain, avg_loss)
    return out


def _rsi_from_avgs(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0.0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    closes: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, List[Optional[float]]]:
    """MACD line, signal line, histogram — all causal."""
    if not (fast < slow):
        raise ValueError("fast period must be < slow period")
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line: List[Optional[float]] = [None] * len(closes)
    for i, (f, s) in enumerate(zip(ema_fast, ema_slow)):
        if f is None or s is None:
            continue
        macd_line[i] = f - s

    # Signal EMA over available MACD values (skip leading Nones by feeding only defined)
    signal_line = _ema_over_optional(macd_line, signal)
    hist: List[Optional[float]] = [None] * len(closes)
    for i, (m, sig) in enumerate(zip(macd_line, signal_line)):
        if m is None or sig is None:
            continue
        hist[i] = m - sig
    return {"macd": macd_line, "signal": signal_line, "histogram": hist}


def _ema_over_optional(values: Sequence[Optional[float]], period: int) -> List[Optional[float]]:
    """EMA that ignores leading Nones; once started, treats gaps as invalid (should not occur)."""
    out: List[Optional[float]] = [None] * len(values)
    buffer: List[float] = []
    prev: Optional[float] = None
    alpha = 2.0 / (period + 1)
    for i, value in enumerate(values):
        if value is None:
            continue
        if prev is None:
            buffer.append(value)
            if len(buffer) == period:
                prev = sum(buffer) / period
                out[i] = prev
            continue
        prev = alpha * value + (1.0 - alpha) * prev
        out[i] = prev
    return out


def true_range(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
) -> List[float]:
    h = _as_float_array(highs)
    l = _as_float_array(lows)
    c = _as_float_array(closes)
    n = len(c)
    if not (len(h) == len(l) == n):
        raise ValueError("highs, lows, closes must be same length")
    tr = np.zeros(n, dtype=np.float64)
    tr[0] = float(h[0] - l[0])
    for i in range(1, n):
        tr[i] = max(
            float(h[i] - l[i]),
            abs(float(h[i] - c[i - 1])),
            abs(float(l[i] - c[i - 1])),
        )
    return tr.tolist()


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> List[Optional[float]]:
    """Wilder ATR."""
    if period < 1:
        raise ValueError("period must be >= 1")
    tr = true_range(highs, lows, closes)
    n = len(tr)
    out: List[Optional[float]] = [None] * n
    if n < period:
        return out
    prev = float(np.mean(tr[:period]))
    out[period - 1] = prev
    for i in range(period, n):
        prev = (prev * (period - 1) + tr[i]) / period
        out[i] = prev
    return out


def bollinger_bands(
    closes: Sequence[float],
    period: int = 20,
    std_mult: float = 2.0,
) -> dict[str, List[Optional[float]]]:
    """Bollinger mid/upper/lower using population std of the trailing window ending at i."""
    if period < 2:
        raise ValueError("period must be >= 2")
    arr = _as_float_array(closes)
    n = len(arr)
    mid: List[Optional[float]] = [None] * n
    upper: List[Optional[float]] = [None] * n
    lower: List[Optional[float]] = [None] * n
    for i in range(period - 1, n):
        window = arr[i - period + 1 : i + 1]
        mean = float(np.mean(window))
        std = float(np.std(window, ddof=0))
        mid[i] = mean
        upper[i] = mean + std_mult * std
        lower[i] = mean - std_mult * std
    return {"mid": mid, "upper": upper, "lower": lower}


def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> dict[str, List[Optional[float]]]:
    """
    Wilder ADX / +DI / -DI.
    Values become available after sufficient warm-up; each point uses only past bars.
    """
    if period < 1:
        raise ValueError("period must be >= 1")
    h = _as_float_array(highs)
    l = _as_float_array(lows)
    c = _as_float_array(closes)
    n = len(c)
    plus_di: List[Optional[float]] = [None] * n
    minus_di: List[Optional[float]] = [None] * n
    adx_line: List[Optional[float]] = [None] * n
    if n < period + 1:
        return {"adx": adx_line, "plus_di": plus_di, "minus_di": minus_di}

    tr = np.asarray(true_range(highs, lows, closes), dtype=np.float64)
    up_move = np.zeros(n)
    down_move = np.zeros(n)
    for i in range(1, n):
        up_move[i] = h[i] - h[i - 1]
        down_move[i] = l[i - 1] - l[i]

    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    for i in range(1, n):
        plus_dm[i] = up_move[i] if up_move[i] > down_move[i] and up_move[i] > 0 else 0.0
        minus_dm[i] = down_move[i] if down_move[i] > up_move[i] and down_move[i] > 0 else 0.0

    # Wilder smooth starting at index `period`
    atr_s = float(np.sum(tr[1 : period + 1]))
    plus_s = float(np.sum(plus_dm[1 : period + 1]))
    minus_s = float(np.sum(minus_dm[1 : period + 1]))

    def _di(num: float, den: float) -> float:
        return 0.0 if den == 0 else 100.0 * num / den

    plus_di[period] = _di(plus_s, atr_s)
    minus_di[period] = _di(minus_s, atr_s)
    dx_values: List[Optional[float]] = [None] * n
    dx_values[period] = _dx(plus_di[period], minus_di[period])

    for i in range(period + 1, n):
        atr_s = atr_s - (atr_s / period) + float(tr[i])
        plus_s = plus_s - (plus_s / period) + float(plus_dm[i])
        minus_s = minus_s - (minus_s / period) + float(minus_dm[i])
        plus_di[i] = _di(plus_s, atr_s)
        minus_di[i] = _di(minus_s, atr_s)
        dx_values[i] = _dx(plus_di[i], minus_di[i])

    # First ADX is SMA of first `period` DX values starting at index `period`
    first_adx_idx = period * 2 - 1
    if first_adx_idx < n:
        dx_seed = [dx_values[i] for i in range(period, period + period) if dx_values[i] is not None]
        if len(dx_seed) == period:
            adx_prev = float(np.mean(dx_seed))
            adx_line[first_adx_idx] = adx_prev
            for i in range(first_adx_idx + 1, n):
                dx_i = dx_values[i]
                if dx_i is None:
                    continue
                adx_prev = (adx_prev * (period - 1) + dx_i) / period
                adx_line[i] = adx_prev

    return {"adx": adx_line, "plus_di": plus_di, "minus_di": minus_di}


def _dx(plus: Optional[float], minus: Optional[float]) -> Optional[float]:
    if plus is None or minus is None:
        return None
    denom = plus + minus
    if denom == 0:
        return 0.0
    return 100.0 * abs(plus - minus) / denom
