"""TA response / config schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from app.ta.structure import StructureSnapshot


class IndicatorPoint(BaseModel):
    index: int
    timestamp: Optional[str] = None
    value: Optional[float] = None


class IndicatorSeries(BaseModel):
    name: str
    values: List[Optional[float]]


class TechnicalAnalysisConfig(BaseModel):
    ema_periods: List[int] = Field(default_factory=lambda: [20, 50, 100, 200])
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    adx_period: int = 14
    atr_period: int = 14
    bb_period: int = 20
    bb_std: float = 2.0
    swing_left: int = 2
    swing_right: int = 2


class LatestIndicators(BaseModel):
    ema_20: Optional[float] = None
    ema_50: Optional[float] = None
    ema_100: Optional[float] = None
    ema_200: Optional[float] = None
    rsi: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    adx: Optional[float] = None
    plus_di: Optional[float] = None
    minus_di: Optional[float] = None
    atr: Optional[float] = None
    bb_mid: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None


class TechnicalAnalysisResult(BaseModel):
    symbol: str
    timeframe: str
    bar_count: int
    as_of_index: int
    as_of_timestamp: Optional[str] = None
    latest: LatestIndicators
    series: dict[str, List[Optional[float]]]
    structure: StructureSnapshot
    config: TechnicalAnalysisConfig
