"""Typed signal schemas for the rule-based strategy engine."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.strategy.config import StrategyConfig


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"
    NO_TRADE = "NO_TRADE"


class SetupLifecycle(str, Enum):
    DETECTED = "DETECTED"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


class SignalStatus(str, Enum):
    DETECTED = "DETECTED"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"


class VolatilityBand(str, Enum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EXTREME = "EXTREME"
    UNKNOWN = "UNKNOWN"


class MarketCondition(str, Enum):
    """Stub market filter — no live news API in Phase 6."""

    NORMAL = "NORMAL"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    UNSAFE = "UNSAFE"
    UNKNOWN = "UNKNOWN"


class EntryZone(BaseModel):
    low: float
    high: float
    preferred: float


class TakeProfitLevel(BaseModel):
    price: float
    rr: float
    label: str


class MarketContext(BaseModel):
    htf_bias: str
    setup_bias: str
    entry_bias: str
    state: str
    alignment_score: int = 0


class ConditionScore(BaseModel):
    key: str
    label: str
    met: bool
    points: float
    max_points: float
    detail: str = ""


class StrategySignal(BaseModel):
    signal_id: str
    setup_id: str
    symbol: str
    timestamp: str
    as_of: str
    direction: SignalDirection
    status: SignalStatus
    score: int
    score_label: str = ""  # e.g. "82/100 strategy condition score"
    entry: Optional[EntryZone] = None
    stop_loss: Optional[float] = None
    targets: List[TakeProfitLevel] = Field(default_factory=list)
    primary_rr: Optional[float] = None
    market_context: MarketContext
    conditions: List[ConditionScore] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    volatility: VolatilityBand = VolatilityBand.UNKNOWN
    market_condition: MarketCondition = MarketCondition.NORMAL
    strategy_version: str
    setup_lifecycle: SetupLifecycle = SetupLifecycle.DETECTED
    expires_at_bar_index: Optional[int] = None
    entry_timeframe: str = "15m"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StrategyAnalyzeResult(BaseModel):
    symbol: str
    as_of: str
    signal: SignalDirection
    score: int
    score_label: str
    status: SignalStatus
    setup_id: Optional[str] = None
    signal_id: Optional[str] = None
    entry: Optional[EntryZone] = None
    stop_loss: Optional[float] = None
    targets: List[TakeProfitLevel] = Field(default_factory=list)
    primary_rr: Optional[float] = None
    market_context: MarketContext
    conditions: List[ConditionScore] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    volatility: VolatilityBand = VolatilityBand.UNKNOWN
    market_condition: MarketCondition = MarketCondition.NORMAL
    strategy_version: str
    config: StrategyConfig
    current: Optional[StrategySignal] = None
    notes: List[str] = Field(default_factory=list)


class StrategyHistoryResponse(BaseModel):
    symbol: str
    count: int
    signals: List[StrategySignal]
