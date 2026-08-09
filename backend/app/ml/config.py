"""ML dataset configuration — research defaults, not optimized."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field


# --- Phase 11.8 a priori triple-barrier constants (do not retune on TEST) ---
TRIPLE_BARRIER_HORIZON_BARS: int = 8
TRIPLE_BARRIER_ATR_MULT: float = 1.0
TRIPLE_BARRIER_ATR_PERIOD: int = 14


class FeatureConfig(BaseModel):
    feature_version: str = "1.0.0"
    include_ta: bool = True
    include_price_action: bool = True
    include_smc: bool = True
    include_mtf: bool = True
    include_strategy: bool = True
    include_time: bool = True
    include_volatility: bool = True
    atr_percentile_lookback: int = 100  # causal window only


class TripleBarrierConfig(BaseModel):
    """ATR-normalized triple-barrier labeling (Phase 11.8)."""

    horizon_bars: int = TRIPLE_BARRIER_HORIZON_BARS
    atr_mult: float = TRIPLE_BARRIER_ATR_MULT
    atr_period: int = TRIPLE_BARRIER_ATR_PERIOD
    # Same-bar touch of both barriers → FLAT (conservative)
    same_bar_both: Literal["FLAT"] = "FLAT"
    # Vertical barrier: no hit within horizon → FLAT
    vertical_label: Literal["FLAT"] = "FLAT"


class LabelConfig(BaseModel):
    label_version: str = "1.0.0"
    # legacy = Phase 8 %-return direction + optional strategy_outcome
    # triple_barrier = Phase 11.8 candle-level UP/DOWN/FLAT
    labeling_mode: Literal["legacy", "triple_barrier"] = "legacy"
    horizons: List[int] = Field(default_factory=lambda: [5, 10, 20, 40])
    direction_threshold_pct: float = 0.0015  # 0.15% move for UP/DOWN (legacy)
    primary_horizon: int = 10
    include_strategy_outcome: bool = True
    include_forward_returns: bool = True
    include_mfe_mae: bool = True
    include_multiclass: bool = True
    triple_barrier: TripleBarrierConfig = Field(default_factory=TripleBarrierConfig)


class DatasetConfig(BaseModel):
    dataset_version: str = "1.0.0"
    symbol: str = "XAUUSD"
    timeframe: str = "15m"
    timezone: str = "UTC"
    warmup_bars: int = 80
    row_step: int = 1  # emit a row every N entry bars
    # Cap causal lookback for TA/SMC/MTF windows (performance; still past-only)
    max_context_bars: int = 400
    train_ratio: float = 0.70
    validation_ratio: float = 0.15
    test_ratio: float = 0.15
    strategy_version: str = "1.0.0"
    feature: FeatureConfig = Field(default_factory=FeatureConfig)
    label: LabelConfig = Field(default_factory=LabelConfig)
    output_dir: str = "data/ml_datasets"


def candle_level_dataset_config(
    *,
    symbol: str = "PAXGUSD",
    timeframe: str = "15m",
    output_dir: str = "data/ml_datasets_candle",
) -> DatasetConfig:
    """Research config for Phase 11.8 — full-history candle labels, no strategy gate."""
    return DatasetConfig(
        dataset_version="2.0.0-candle-tb",
        symbol=symbol,
        timeframe=timeframe,
        warmup_bars=80,
        row_step=1,
        max_context_bars=350,
        train_ratio=0.70,
        validation_ratio=0.15,
        test_ratio=0.15,
        strategy_version="1.0.0",
        feature=FeatureConfig(
            feature_version="1.0.0",
            include_strategy=False,
            include_ta=True,
            include_smc=True,
            include_mtf=True,
        ),
        label=LabelConfig(
            label_version="2.0.0-triple-barrier",
            labeling_mode="triple_barrier",
            horizons=[TRIPLE_BARRIER_HORIZON_BARS],
            primary_horizon=TRIPLE_BARRIER_HORIZON_BARS,
            include_strategy_outcome=False,
            include_forward_returns=True,
            include_mfe_mae=True,
            include_multiclass=False,
            triple_barrier=TripleBarrierConfig(),
        ),
        output_dir=output_dir,
    )
