"""Risk / TradePlan schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.instruments.schemas import InstrumentSpec
from app.risk.config import AccountRiskConfig
from app.risk.costs import CostBreakdown
from app.strategy.schemas import SignalDirection, TakeProfitLevel


class RiskStatus(str, Enum):
    RISK_ACCEPTED = "RISK_ACCEPTED"
    RISK_REJECTED = "RISK_REJECTED"
    INVALID = "INVALID"
    INSUFFICIENT_MARGIN = "INSUFFICIENT_MARGIN"
    POSITION_LIMIT_EXCEEDED = "POSITION_LIMIT_EXCEEDED"
    DAILY_LIMIT_REACHED = "DAILY_LIMIT_REACHED"
    TRADING_BLOCKED = "TRADING_BLOCKED"
    MODEL_INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    COST_DATA_UNAVAILABLE = "COST_DATA_UNAVAILABLE"
    SKIPPED_NO_SIGNAL = "SKIPPED_NO_SIGNAL"


class TargetRiskRow(BaseModel):
    label: str
    price: float
    gross_reward_usd: float
    net_reward_usd: float
    gross_rr: float
    net_rr: float


class TradePlan(BaseModel):
    instrument: str
    direction: SignalDirection
    signal_status: str
    rule_score: Optional[int] = None
    ml_prediction: Optional[str] = None
    ml_confidence: Optional[float] = None

    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    targets: List[TakeProfitLevel] = Field(default_factory=list)

    account_balance: float
    currency: str
    risk_percent: float
    risk_amount: float
    risk_amount_usd: float

    stop_distance: Optional[float] = None
    stop_distance_pct: Optional[float] = None

    quantity: float = 0.0
    raw_quantity: float = 0.0
    notional_value: float = 0.0
    leverage: float = 1.0
    required_margin: float = 0.0
    required_margin_usd: float = 0.0

    spread_cost: float = 0.0
    slippage_cost: float = 0.0
    trading_fee: float = 0.0
    funding_cost: float = 0.0
    estimated_total_cost: float = 0.0
    cost_currency: str = "USD"

    gross_rr: Optional[float] = None
    net_rr: Optional[float] = None
    target_rows: List[TargetRiskRow] = Field(default_factory=list)

    risk_status: RiskStatus = RiskStatus.INVALID
    reasons: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    instrument_spec: Optional[InstrumentSpec] = None
    account: Optional[AccountRiskConfig] = None
    costs: Optional[CostBreakdown] = None
    notes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RiskAnalyzeResult(BaseModel):
    trade_plan: TradePlan
    label: str = "RESEARCH ONLY — not live execution"
