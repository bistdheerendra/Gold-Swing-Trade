"""Strategy configuration — research defaults, not optimized parameters."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreWeights(BaseModel):
    """
    Condition weights summing to ~100 research points.

    These are NOT win probabilities and are NOT optimized against test data.
    """

    higher_tf_bias: float = 20
    structure_4h: float = 15
    setup_1h: float = 15
    liquidity_sweep: float = 15
    bos_choch: float = 10
    ob_demand_supply: float = 10
    fvg: float = 5
    premium_discount: float = 5
    entry_15m: float = 5

    def total(self) -> float:
        return (
            self.higher_tf_bias
            + self.structure_4h
            + self.setup_1h
            + self.liquidity_sweep
            + self.bos_choch
            + self.ob_demand_supply
            + self.fvg
            + self.premium_discount
            + self.entry_15m
        )


class StrategyConfig(BaseModel):
    """Central strategy knobs — do not scatter constants in detectors."""

    strategy_version: str = "1.0.0"

    # Thresholds on condition score (0..100) — not probability
    strong_signal_threshold: float = 80
    signal_threshold: float = 65
    wait_threshold: float = 50

    min_rr: float = 1.5
    sl_buffer: float = 0.5  # absolute price buffer beyond structure
    sl_atr_buffer_mult: float = 0.15  # extra ATR fraction for SL buffer
    max_signal_age_bars: int = 12  # entry TF bars before EXPIRED

    liquidity_required: bool = False
    require_structure_confirmation: bool = True
    require_entry_confirmation: bool = False  # soft: missing entry → WAIT via score
    minimum_htf_alignment: bool = True  # 4H must agree with trade direction (or pullback)

    # Volatility filter
    atr_filter_enabled: bool = True
    extreme_atr_multiplier: float = 3.0  # vs median ATR → EXTREME → NO_TRADE
    high_atr_multiplier: float = 1.75
    high_volatility_penalty: float = 8.0

    # Market condition filter (stub — no live news API)
    reject_unsafe_market: bool = True

    score_weights: ScoreWeights = Field(default_factory=ScoreWeights)
    tp_method: str = "liquidity_then_swing"  # documented in docs/strategy.md

    # Lookbacks for recent events (bars on that TF)
    recent_sweep_bars: int = 40
    recent_break_bars: int = 60
    entry_confirm_bars: int = 24
