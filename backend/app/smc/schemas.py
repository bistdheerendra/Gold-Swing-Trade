"""Typed SMC schemas and configuration."""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SmcDirection(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class SmcEventType(str, Enum):
    SWING_HIGH = "swing_high"
    SWING_LOW = "swing_low"
    BOS = "bos"
    CHOCH = "choch"
    BULLISH_FVG = "bullish_fvg"
    BEARISH_FVG = "bearish_fvg"
    ORDER_BLOCK = "order_block"
    DEMAND_ZONE = "demand_zone"
    SUPPLY_ZONE = "supply_zone"
    BUY_SIDE_LIQUIDITY = "buy_side_liquidity"
    SELL_SIDE_LIQUIDITY = "sell_side_liquidity"
    LIQUIDITY_SWEEP = "liquidity_sweep"


class FvgLifecycle(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    INVALIDATED = "INVALIDATED"


class DealingZone(str, Enum):
    PREMIUM = "PREMIUM"
    EQUILIBRIUM = "EQUILIBRIUM"
    DISCOUNT = "DISCOUNT"
    UNKNOWN = "UNKNOWN"


class SmcConfig(BaseModel):
    swing_left: int = 2
    swing_right: int = 2
    break_on_close: bool = True
    break_on_wick: bool = False
    min_break_distance: float = 0.0
    min_break_percentage: float = 0.0
    fvg_min_size: float = 0.0
    ob_lookback: int = 10
    ob_min_body_ratio: float = 0.5
    ob_require_bos: bool = True
    ob_displacement_atr_mult: float = 0.0
    liq_cluster_tolerance: float = 0.15
    liq_min_touches: int = 2
    liq_lookback_swings: int = 20
    sweep_min_penetration: float = 0.0
    sweep_require_close_reclaim: bool = True
    sweep_max_bars_for_reclaim: int = 3
    eq_band_pct: float = 0.02


class SmcEvent(BaseModel):
    id: str
    type: SmcEventType
    direction: SmcDirection
    timeframe: str
    created_index: int
    confirm_index: int
    valid: bool = True
    high: Optional[float] = None
    low: Optional[float] = None
    price: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BosEvent(SmcEvent):
    break_index: int
    broken_level: float
    source_swing_index: int


class FvgEvent(SmcEvent):
    size: float
    lifecycle: FvgLifecycle = FvgLifecycle.ACTIVE
    filled: bool = False
    fill_index: Optional[int] = None


class ZoneEvent(SmcEvent):
    strength: float = 0.0
    mitigated: bool = False
    mitigation_index: Optional[int] = None
    origin_index: int = 0


class LiquidityPool(SmcEvent):
    touches: int = 0
    member_pivots: List[int] = Field(default_factory=list)


class SweepEvent(SmcEvent):
    liquidity_level: float
    sweep_index: int
    penetration: float


class DealingRange(BaseModel):
    range_high: Optional[float] = None
    range_low: Optional[float] = None
    equilibrium: Optional[float] = None
    current_price: Optional[float] = None
    zone: DealingZone = DealingZone.UNKNOWN
    distance_from_equilibrium: Optional[float] = None
    high_confirm_index: Optional[int] = None
    low_confirm_index: Optional[int] = None


class SmcStructureSummary(BaseModel):
    bias: SmcDirection = SmcDirection.NEUTRAL
    swing_highs: List[SmcEvent] = Field(default_factory=list)
    swing_lows: List[SmcEvent] = Field(default_factory=list)
    last_swing_high: Optional[SmcEvent] = None
    last_swing_low: Optional[SmcEvent] = None


class SmcAnalysisResult(BaseModel):
    symbol: str
    timeframe: str
    bar_count: int
    as_of_index: int
    as_of_timestamp: Optional[str] = None
    config: SmcConfig
    structure: SmcStructureSummary
    bos: List[BosEvent] = Field(default_factory=list)
    choch: List[BosEvent] = Field(default_factory=list)
    fvg: List[FvgEvent] = Field(default_factory=list)
    order_blocks: List[ZoneEvent] = Field(default_factory=list)
    demand_zones: List[ZoneEvent] = Field(default_factory=list)
    supply_zones: List[ZoneEvent] = Field(default_factory=list)
    liquidity: List[LiquidityPool] = Field(default_factory=list)
    liquidity_sweeps: List[SweepEvent] = Field(default_factory=list)
    dealing_range: DealingRange
    smc_score: int = 0
    summary: dict[str, Any] = Field(default_factory=dict)
