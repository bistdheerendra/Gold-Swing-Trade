"""Shared break helpers for BOS / CHoCH."""

from __future__ import annotations

from app.smc.schemas import SmcConfig, SmcDirection


def break_buffer(level: float, config: SmcConfig) -> float:
    pct = abs(level) * (config.min_break_percentage / 100.0)
    return max(config.min_break_distance, pct)


def is_bullish_break(
    *,
    high: float,
    close: float,
    level: float,
    config: SmcConfig,
) -> bool:
    buf = break_buffer(level, config)
    threshold = level + buf
    if config.break_on_close or not config.break_on_wick:
        return close > threshold
    return high > threshold


def is_bearish_break(
    *,
    low: float,
    close: float,
    level: float,
    config: SmcConfig,
) -> bool:
    buf = break_buffer(level, config)
    threshold = level - buf
    if config.break_on_close or not config.break_on_wick:
        return close < threshold
    return low < threshold


def opposite(direction: SmcDirection) -> SmcDirection:
    if direction == SmcDirection.BULLISH:
        return SmcDirection.BEARISH
    if direction == SmcDirection.BEARISH:
        return SmcDirection.BULLISH
    return SmcDirection.NEUTRAL
