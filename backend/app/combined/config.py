"""Combined signal configuration (Phase 10)."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SignalMode(str, Enum):
    RULE_ONLY = "RULE_ONLY"
    ML_FILTER = "ML_FILTER"
    COMBINED = "COMBINED"  # alias of ML_FILTER decision path for backtests


class MlFallbackMode(str, Enum):
    """When ML is unavailable / incompatible."""

    FALLBACK_RULE = "FALLBACK_RULE"  # use Phase 6 signal, mark ml_status
    WAIT = "WAIT"


class ConflictAction(str, Enum):
    NO_TRADE = "NO_TRADE"
    WAIT = "WAIT"


class CombinedSignalConfig(BaseModel):
    """
    Defaults: ML filter on Phase 6 setups only.
    min_ml_confidence must come from Phase 9 VALIDATION (never TEST).
    """

    min_ml_confidence: float = Field(default=0.60, ge=0.0, le=1.0)
    require_direction_alignment: bool = True
    allow_neutral: bool = True
    rule_min_score: float = Field(default=0.0, ge=0.0, le=100.0)
    conflict_action: ConflictAction = ConflictAction.NO_TRADE
    ml_fallback: MlFallbackMode = MlFallbackMode.FALLBACK_RULE
    rule_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    ml_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    feature_version_expected: str = "1.0.0"
    model_id: Optional[str] = None
    probability_calibrated: bool = False  # Phase 9 calibration is research; default false
    notes: list[str] = Field(
        default_factory=lambda: [
            "RESEARCH ONLY — not broker execution",
            "ML confidence is not a guaranteed win probability",
            "min_ml_confidence must be frozen from VALIDATION, never TEST",
        ]
    )
