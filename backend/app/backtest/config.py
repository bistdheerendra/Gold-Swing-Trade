"""Backtest configuration — measurement defaults, not optimized parameters."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AmbiguityPolicy(str, Enum):
    """Same-candle Entry/SL/TP ambiguity (OHLC cannot resolve path)."""

    CONSERVATIVE = "CONSERVATIVE"  # assume SL before TP
    SKIP = "SKIP"  # do not resolve; leave open / mark ambiguous skip close


class TpMode(str, Enum):
    FULL_AT_TP1 = "FULL_AT_TP1"
    TP1_THEN_RUNNER = "TP1_THEN_RUNNER"  # structural: exit at TP1 for Phase 7 simplicity
    TP2 = "TP2"
    TP3 = "TP3"


class CostMode(str, Enum):
    ZERO_COST = "ZERO_COST"
    REALISTIC_COST = "REALISTIC_COST"


class RiskSizingMode(str, Enum):
    """
    FIXED_1R — normalized research: 1R = initial_equity * risk_fraction (no compounding).
    RISK_PERCENT — account simulation: 1R = current_equity * risk_fraction (compounds).
    """

    FIXED_1R = "FIXED_1R"
    RISK_PERCENT = "RISK_PERCENT"


class BacktestCostConfig(BaseModel):
    """
    Trading costs applied by the backtester only — not inside strategy logic.

    Points are absolute price units on XAUUSD (e.g. 0.30 = $0.30).
    """

    mode: CostMode = CostMode.REALISTIC_COST
    spread_points: float = 0.30
    slippage_points: float = 0.10
    commission_per_trade: float = 0.0  # flat currency units (equity currency)

    def effective_spread(self) -> float:
        return 0.0 if self.mode == CostMode.ZERO_COST else self.spread_points

    def effective_slippage(self) -> float:
        return 0.0 if self.mode == CostMode.ZERO_COST else self.slippage_points

    def effective_commission(self) -> float:
        return 0.0 if self.mode == CostMode.ZERO_COST else self.commission_per_trade


class BacktestExecutionConfig(BaseModel):
    ambiguity_policy: AmbiguityPolicy = AmbiguityPolicy.CONSERVATIVE
    tp_mode: TpMode = TpMode.FULL_AT_TP1
    max_signal_age_bars: Optional[int] = None  # override strategy; None → strategy config
    allow_pyramiding: bool = False  # one active position at a time


class DataSplitConfig(BaseModel):
    """Chronological split — never shuffle time series."""

    train_ratio: float = 0.70
    validation_ratio: float = 0.15
    test_ratio: float = 0.15
    # Optional absolute date windows (UTC). If set, override ratios for that segment run.
    train_start: Optional[str] = None
    train_end: Optional[str] = None
    validation_start: Optional[str] = None
    validation_end: Optional[str] = None
    test_start: Optional[str] = None
    test_end: Optional[str] = None


class BacktestConfig(BaseModel):
    symbol: str = "XAUUSD"
    entry_timeframe: str = "15m"
    initial_equity: float = 100_000.0
    # FIXED_1R: 1R from initial equity (research normalization).
    # RISK_PERCENT: 1R from current equity (account-style simulation).
    risk_fraction_per_trade: float = 0.01  # e.g. 1%
    risk_mode: RiskSizingMode = RiskSizingMode.FIXED_1R
    cost: BacktestCostConfig = Field(default_factory=BacktestCostConfig)
    execution: BacktestExecutionConfig = Field(default_factory=BacktestExecutionConfig)
    split: DataSplitConfig = Field(default_factory=DataSplitConfig)
    strategy_version: str = "1.0.0"
    timezone: str = "UTC"
    # Warmup bars on entry TF before emitting signals
    warmup_bars: int = 80
    # Max causal lookback per TF passed into strategy (performance; still past-only)
    max_context_bars: int = 500
    # Step every N entry bars (1 = every candle). Keep 1 for correctness.
    step: int = 1
    # Phase 10: RULE_ONLY | ML_FILTER | COMBINED
    signal_mode: str = "RULE_ONLY"
    model_id: Optional[str] = None
    min_ml_confidence: Optional[float] = None  # freeze from validation; None → model default
