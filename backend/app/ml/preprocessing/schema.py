"""Feature type schema for preprocessing."""

from __future__ import annotations

from typing import Dict, List, Sequence

from pydantic import BaseModel, Field


class FeatureTypeSchema(BaseModel):
    version: str = "1.0.0"
    numeric: List[str] = Field(default_factory=list)
    categorical: List[str] = Field(default_factory=list)
    boolean: List[str] = Field(default_factory=list)

    def all_features(self) -> List[str]:
        return list(self.numeric) + list(self.categorical) + list(self.boolean)


BOOLEAN_HINTS = {
    "bullish_candle",
    "bearish_candle",
    "bullish_fvg_present",
    "bearish_fvg_present",
    "bullish_ob_present",
    "bearish_ob_present",
    "demand_present",
    "supply_present",
    "cond_htf_alignment",
    "cond_structure_confirmation",
    "cond_liquidity_confirmation",
    "cond_ob_confirmation",
    "cond_fvg_confirmation",
    "cond_entry_confirmation",
}

CATEGORICAL_HINTS = {
    "ema_alignment",
    "structure_bias",
    "last_bos_direction",
    "last_choch_direction",
    "liquidity_sweep_direction",
    "premium_discount_state",
    "htf_1d_bias",
    "htf_4h_bias",
    "htf_1h_bias",
    "htf_30m_bias",
    "entry_15m_bias",
    "higher_timeframe_bias",
    "setup_bias",
    "entry_bias",
    "market_state_code",
    "strategy_direction",
    "strategy_state_code",
    "volatility_filter_state",
    "hour_utc",
    "day_of_week",
    "day_of_month",
    "month",
}


def infer_feature_schema(feature_names: Sequence[str]) -> FeatureTypeSchema:
    numeric, categorical, boolean = [], [], []
    for n in feature_names:
        if n in BOOLEAN_HINTS or n.startswith("cond_"):
            boolean.append(n)
        elif n in CATEGORICAL_HINTS:
            categorical.append(n)
        else:
            numeric.append(n)
    return FeatureTypeSchema(numeric=numeric, categorical=categorical, boolean=boolean)
