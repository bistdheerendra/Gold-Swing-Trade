"""MTF schemas and bias configuration."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BiasLabel(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class StructureLabel(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    RANGING = "RANGING"
    NEUTRAL = "NEUTRAL"


class MtfState(str, Enum):
    TRENDING = "TRENDING"
    PULLBACK = "PULLBACK"
    REVERSAL_RISK = "REVERSAL_RISK"
    RANGING = "RANGING"
    CONFLICT = "CONFLICT"
    NEUTRAL = "NEUTRAL"


class BiasWeights(BaseModel):
    """Configurable research weights — not proven trading edge."""

    ema_weight: float = 15
    structure_weight: float = 25
    bos_weight: float = 20
    choch_weight: float = 15
    momentum_weight: float = 10
    liquidity_weight: float = 15

    def total(self) -> float:
        return (
            self.ema_weight
            + self.structure_weight
            + self.bos_weight
            + self.choch_weight
            + self.momentum_weight
            + self.liquidity_weight
        )


class TimeframeAnalysis(BaseModel):
    timeframe: str
    role: str
    trend: BiasLabel
    structure: StructureLabel
    momentum: BiasLabel
    volatility: str  # LOW / NORMAL / HIGH / UNKNOWN
    smc_bias: BiasLabel
    last_bos: Optional[str] = None
    last_choch: Optional[str] = None
    active_fvg: Optional[str] = None
    active_order_block: Optional[str] = None
    liquidity_state: Optional[str] = None
    dealing_range: Optional[str] = None
    ta_score: int = 0  # -100..100 from TA factors only
    smc_score: int = 0  # 0..100 from SMC engine (unsigned dashboard score)
    bias_score: int = 0  # -100..100 combined


class MtfLayerSummary(BaseModel):
    bias: BiasLabel
    timeframe: str
    bias_score: int = 0


class MultiTimeframeResult(BaseModel):
    symbol: str
    as_of: str
    timeframes: Dict[str, TimeframeAnalysis]
    macro: MtfLayerSummary
    structure: MtfLayerSummary
    setup: MtfLayerSummary
    timing: MtfLayerSummary = Field(
        default_factory=lambda: MtfLayerSummary(
            bias=BiasLabel.NEUTRAL, timeframe="30m", bias_score=0
        )
    )
    entry: MtfLayerSummary
    higher_timeframe_bias: BiasLabel
    setup_bias: BiasLabel
    entry_bias: BiasLabel
    alignment_score: int  # 0..100
    state: MtfState
    weights: BiasWeights
    notes: List[str] = Field(default_factory=list)
