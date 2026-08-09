"""Feature catalog definitions (metadata only)."""

from __future__ import annotations

from typing import List

from app.ml.schemas import FeatureMeta, NormalizationHint


def feature_catalog(timeframe: str = "15m") -> List[FeatureMeta]:
    """Documented feature set v1.0.0 — all causal when built via FeatureBuilder."""
    tf = timeframe
    cat: List[FeatureMeta] = []

    def add(
        name: str,
        dtype: str,
        source: str,
        desc: str,
        *,
        norm: NormalizationHint = NormalizationHint.NONE,
        missing: str = "null",
        tframe: str | None = None,
    ) -> None:
        cat.append(
            FeatureMeta(
                name=name,
                dtype=dtype,
                source=source,
                timeframe=tframe or tf,
                description=desc,
                causal=True,
                normalization=norm,
                missing_behavior=missing,
            )
        )

    # TA
    for p in (20, 50, 100, 200):
        add(f"ema{p}_distance_pct", "float", "ta", f"Close vs EMA{p} %", norm=NormalizationHint.STANDARDIZE)
        add(f"ema{p}_slope", "float", "ta", f"EMA{p} slope over 3 bars", norm=NormalizationHint.STANDARDIZE)
    add("ema20_vs_50", "float", "ta", "EMA20-EMA50 / price")
    add("ema50_vs_100", "float", "ta", "EMA50-EMA100 / price")
    add("ema100_vs_200", "float", "ta", "EMA100-EMA200 / price")
    add("ema_alignment", "int", "ta", "Bullish stack +1 / mixed 0 / bear -1", norm=NormalizationHint.CATEGORICAL)
    add("rsi", "float", "ta", "RSI(14)", norm=NormalizationHint.MINMAX)
    add("rsi_distance_from_50", "float", "ta", "RSI-50")
    add("macd", "float", "ta", "MACD line")
    add("macd_signal", "float", "ta", "MACD signal")
    add("macd_histogram", "float", "ta", "MACD histogram")
    add("macd_histogram_slope", "float", "ta", "Histogram delta")
    add("adx", "float", "ta", "ADX(14)")
    add("atr", "float", "ta", "ATR(14)")
    add("atr_pct", "float", "ta", "ATR/close %")
    add("atr_percentile", "float", "ta", "Causal ATR percentile in lookback", missing="null")
    add("bb_position", "float", "ta", "Close position in Bollinger band")
    add("bb_width", "float", "ta", "BB width / mid")

    # Price action
    for n in (
        "body_size_pct",
        "upper_wick_pct",
        "lower_wick_pct",
        "range_pct",
        "close_position_in_range",
        "bullish_candle",
        "bearish_candle",
    ):
        add(n, "float" if "candle" not in n else "int", "price", n)

    # SMC
    for n, d in [
        ("structure_bias", "SMC structure bias +1/0/-1"),
        ("last_bos_direction", "Last BOS direction"),
        ("last_bos_age", "Bars since last BOS"),
        ("last_choch_direction", "Last CHoCH direction"),
        ("last_choch_age", "Bars since last CHoCH"),
        ("bullish_fvg_present", "Active bullish FVG"),
        ("bearish_fvg_present", "Active bearish FVG"),
        ("nearest_bullish_fvg_distance_pct", "Dist to bullish FVG %"),
        ("nearest_bearish_fvg_distance_pct", "Dist to bearish FVG %"),
        ("bullish_ob_present", "Bullish OB present"),
        ("bearish_ob_present", "Bearish OB present"),
        ("nearest_bullish_ob_distance_pct", "Dist to bullish OB %"),
        ("nearest_bearish_ob_distance_pct", "Dist to bearish OB %"),
        ("demand_present", "Demand zone present"),
        ("supply_present", "Supply zone present"),
        ("buy_side_liquidity_distance_pct", "BSL distance %"),
        ("sell_side_liquidity_distance_pct", "SSL distance %"),
        ("liquidity_sweep_direction", "Recent sweep direction"),
        ("liquidity_sweep_age", "Bars since sweep"),
        ("premium_discount_state", "PREMIUM=1 EQ=0 DISCOUNT=-1"),
        ("distance_from_equilibrium_pct", "Dist from EQ %"),
    ]:
        add(n, "float", "smc", d, missing="null if absent")

    # MTF
    for n in (
        "htf_1d_bias",
        "htf_4h_bias",
        "htf_1h_bias",
        "htf_30m_bias",
        "entry_15m_bias",
        "mtf_alignment_score",
        "higher_timeframe_bias",
        "setup_bias",
        "entry_bias",
        "market_state_code",
    ):
        add(n, "float", "mtf", n, tframe="multi")

    # Strategy
    for n in (
        "strategy_score",
        "strategy_direction",
        "strategy_state_code",
        "cond_htf_alignment",
        "cond_structure_confirmation",
        "cond_liquidity_confirmation",
        "cond_ob_confirmation",
        "cond_fvg_confirmation",
        "cond_entry_confirmation",
        "rr_candidate",
        "volatility_filter_state",
    ):
        add(n, "float", "strategy", n)

    # Time
    for n in ("hour_utc", "day_of_week", "day_of_month", "month"):
        add(n, "int", "time", n, norm=NormalizationHint.CATEGORICAL, tframe="calendar")

    return cat
