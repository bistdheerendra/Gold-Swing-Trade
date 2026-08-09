"""Deterministic Rule + ML decision matrix (Phase 10)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.combined.config import CombinedSignalConfig, ConflictAction
from app.combined.schemas import MlStatus
from app.strategy.schemas import SignalDirection


@dataclass
class DecisionOutcome:
    direction: SignalDirection
    ml_status: MlStatus
    reasons: List[str]


def decide(
    *,
    rule: SignalDirection,
    rule_score: int,
    ml_prediction: Optional[str],
    ml_confidence: Optional[float],
    config: CombinedSignalConfig,
    ml_available: bool = True,
    ml_compatible: bool = True,
) -> DecisionOutcome:
    """
    ML never invents BUY/SELL when rule is WAIT / NO_TRADE.
    ML only ACCEPT / REJECT / REQUEST WAIT on rule setups.
    """
    # Rule gates first
    if rule == SignalDirection.WAIT:
        return DecisionOutcome(
            SignalDirection.WAIT, MlStatus.SKIPPED, ["Rule engine: WAIT — ML does not create trades."]
        )
    if rule == SignalDirection.NO_TRADE:
        return DecisionOutcome(
            SignalDirection.NO_TRADE,
            MlStatus.SKIPPED,
            ["Rule engine: NO_TRADE — ML does not create trades."],
        )

    if rule_score < config.rule_min_score:
        return DecisionOutcome(
            SignalDirection.WAIT,
            MlStatus.SKIPPED,
            [f"Rule score {rule_score} below rule_min_score {config.rule_min_score}."],
        )

    if not ml_compatible:
        return _fallback(
            rule,
            MlStatus.INCOMPATIBLE,
            ["MODEL_INCOMPATIBLE — feature/preprocessing schema mismatch. No ML prediction."],
            config,
        )

    if not ml_available or ml_prediction is None or ml_confidence is None:
        return _fallback(
            rule,
            MlStatus.UNAVAILABLE,
            ["ML_UNAVAILABLE — falling back per config."],
            config,
        )

    pred = str(ml_prediction).upper()
    conf = float(ml_confidence)
    rule_dir = rule.value  # BUY / SELL

    # Conflict
    if config.require_direction_alignment and pred in ("BUY", "SELL") and pred != rule_dir:
        action = (
            SignalDirection.NO_TRADE
            if config.conflict_action == ConflictAction.NO_TRADE
            else SignalDirection.WAIT
        )
        return DecisionOutcome(
            action,
            MlStatus.REJECTED,
            [
                f"ML direction conflicts with rule-based setup (rule={rule_dir}, ml={pred}, "
                f"confidence={conf:.2f})."
            ],
        )

    # Neutral ML
    if pred == "NEUTRAL":
        if config.allow_neutral:
            return DecisionOutcome(
                SignalDirection.WAIT,
                MlStatus.LOW_CONFIDENCE,
                [f"ML NEUTRAL (confidence={conf:.2f}) — waiting for clearer confirmation."],
            )
        return DecisionOutcome(
            SignalDirection.NO_TRADE if config.conflict_action == ConflictAction.NO_TRADE else SignalDirection.WAIT,
            MlStatus.REJECTED,
            ["ML NEUTRAL and allow_neutral=false."],
        )

    # Aligned direction
    if pred == rule_dir:
        if conf >= config.min_ml_confidence:
            return DecisionOutcome(
                rule,
                MlStatus.CONFIRMED,
                [
                    f"ML confirms rule-based setup ({pred}, confidence={conf:.2f} "
                    f">= threshold {config.min_ml_confidence:.2f})."
                ],
            )
        return DecisionOutcome(
            SignalDirection.WAIT,
            MlStatus.LOW_CONFIDENCE,
            [
                f"ML confirmation below configured confidence threshold "
                f"({conf:.2f} < {config.min_ml_confidence:.2f})."
            ],
        )

    # Unexpected label
    return DecisionOutcome(
        SignalDirection.WAIT,
        MlStatus.REJECTED,
        [f"Unhandled ML prediction '{pred}' — defaulting to WAIT."],
    )


def _fallback(
    rule: SignalDirection,
    status: MlStatus,
    reasons: List[str],
    config: CombinedSignalConfig,
) -> DecisionOutcome:
    from app.combined.config import MlFallbackMode

    if config.ml_fallback == MlFallbackMode.WAIT:
        return DecisionOutcome(SignalDirection.WAIT, status, reasons + ["Fallback: WAIT."])
    return DecisionOutcome(
        rule,
        status,
        reasons + [f"Fallback: Phase 6 signal ({rule.value}) with ml_status marked."],
    )


def combined_score(
    rule_score: int,
    ml_confidence: Optional[float],
    config: CombinedSignalConfig,
) -> Optional[float]:
    if ml_confidence is None:
        return None
    return round(
        (rule_score / 100.0) * config.rule_weight + float(ml_confidence) * config.ml_weight,
        6,
    )
