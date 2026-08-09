"""Market condition + volatility filters (no live news API)."""

from __future__ import annotations

from typing import Optional, Sequence

from app.strategy.config import StrategyConfig
from app.strategy.schemas import MarketCondition, VolatilityBand
from app.ta.schemas import TechnicalAnalysisResult


class MarketConditionFilter:
    """
    Abstraction for news / session / event risk.

    Phase 6: defaults to NORMAL. Live news integration is explicitly out of scope.
    Strategy may reject UNSAFE when configured.
    """

    def __init__(self, condition: MarketCondition = MarketCondition.NORMAL) -> None:
        self._condition = condition

    def evaluate(self) -> MarketCondition:
        return self._condition

    def set_condition(self, condition: MarketCondition) -> None:
        self._condition = condition


def classify_volatility(
    ta: Optional[TechnicalAnalysisResult],
    config: StrategyConfig,
    *,
    atr_history: Optional[Sequence[Optional[float]]] = None,
) -> VolatilityBand:
    """
    Classify ATR vs recent median.

    NORMAL / HIGH / EXTREME / UNKNOWN — HIGH applies score penalty; EXTREME can NO_TRADE.
    """
    if ta is None or ta.latest.atr is None or ta.latest.atr <= 0:
        return VolatilityBand.UNKNOWN

    atr = float(ta.latest.atr)
    series = atr_history
    if series is None and ta.series:
        series = ta.series.get("atr")  # type: ignore[assignment]

    median = _median_positive(series) if series else None
    if median is None or median <= 0:
        # Fallback: treat as NORMAL when we lack history
        return VolatilityBand.NORMAL

    ratio = atr / median
    if ratio >= config.extreme_atr_multiplier:
        return VolatilityBand.EXTREME
    if ratio >= config.high_atr_multiplier:
        return VolatilityBand.HIGH
    return VolatilityBand.NORMAL


def _median_positive(values: Sequence[Optional[float]]) -> Optional[float]:
    cleaned = [float(v) for v in values if v is not None and v > 0]
    if not cleaned:
        return None
    cleaned.sort()
    mid = len(cleaned) // 2
    if len(cleaned) % 2:
        return cleaned[mid]
    return (cleaned[mid - 1] + cleaned[mid]) / 2.0
