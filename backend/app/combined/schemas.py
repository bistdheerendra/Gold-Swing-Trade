"""Combined signal schemas (Phase 10)."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.strategy.schemas import (
    EntryZone,
    MarketContext,
    SignalDirection,
    SignalStatus,
    StrategyAnalyzeResult,
    TakeProfitLevel,
)


class MlStatus(str, Enum):
    CONFIRMED = "ML_CONFIRMED"
    REJECTED = "ML_REJECTED"
    LOW_CONFIDENCE = "ML_LOW_CONFIDENCE"
    UNAVAILABLE = "ML_UNAVAILABLE"
    INCOMPATIBLE = "MODEL_INCOMPATIBLE"
    SKIPPED = "ML_SKIPPED"  # rule was WAIT / NO_TRADE
    RULE_ONLY = "RULE_ONLY"


class CombinedSignalResult(BaseModel):
    signal_id: Optional[str] = None
    setup_id: Optional[str] = None
    symbol: str
    timeframe: str = "15m"
    as_of: str
    timestamp: str

    direction: SignalDirection  # final combined
    status: SignalStatus = SignalStatus.DETECTED
    rule_signal: SignalDirection
    rule_score: int

    ml_prediction: Optional[str] = None  # BUY | SELL | NEUTRAL
    ml_confidence: Optional[float] = None
    ml_model_id: Optional[str] = None
    ml_model_version: Optional[str] = None
    ml_status: MlStatus = MlStatus.SKIPPED
    probability_calibrated: bool = False

    combined_score: Optional[float] = None
    combined_score_formula: str = (
        "combined_score = rule_score/100 * rule_weight + ml_confidence * ml_weight "
        "(NOT a probability)"
    )

    entry: Optional[EntryZone] = None
    stop_loss: Optional[float] = None
    targets: List[TakeProfitLevel] = Field(default_factory=list)
    primary_rr: Optional[float] = None

    reasons: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    rule_reasons: List[str] = Field(default_factory=list)
    ml_reasons: List[str] = Field(default_factory=list)
    market_context: Optional[MarketContext] = None

    strategy_version: str = "1.0.0"
    feature_version: str = "1.0.0"
    preprocessing_version: Optional[str] = None
    label_version: Optional[str] = None
    dataset_version: Optional[str] = None

    rule_result: Optional[StrategyAnalyzeResult] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: List[str] = Field(default_factory=list)

    def as_strategy_result(self) -> StrategyAnalyzeResult:
        """Adapter for Phase 7 simulator — final direction only."""
        base = self.rule_result
        if base is None:
            raise ValueError("rule_result missing")
        return base.model_copy(
            update={
                "signal": self.direction,
                "reasons": list(self.reasons),
                "risks": list(self.risks),
                "notes": list(base.notes) + list(self.notes) + [
                    f"ml_status={self.ml_status.value}",
                    f"combined_direction={self.direction.value}",
                ],
            }
        )
