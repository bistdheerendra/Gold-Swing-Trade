# ML Features Catalog (v1.0.0)

All features are **causal** when built by `FeatureBuilder` (engines receive `as_of` / truncated windows; SMC events require `confirm_index <= index`).

| Name | Type | Source | Notes | Missing |
|------|------|--------|-------|---------|
| ema{N}_distance_pct | float | TA | Close vs EMA N % | null |
| ema{N}_slope | float | TA | 3-bar EMA delta | null |
| ema20_vs_50 / ema50_vs_100 / ema100_vs_200 | float | TA | Spread / price | null |
| ema_alignment | int | TA | +1 stack / 0 / -1 | null |
| rsi, rsi_distance_from_50 | float | TA | RSI(14) | null |
| macd, macd_signal, macd_histogram, macd_histogram_slope | float | TA | | null |
| adx, atr, atr_pct, atr_percentile | float | TA | Percentile uses **past window only** | null |
| bb_position, bb_width | float | TA | | null |
| body/wick/range_pct, close_position_in_range, bullish/bearish_candle | float/int | Price | Current candle only | — |
| structure_bias, BOS/CHoCH dir+age, FVG/OB/liq, premium_discount… | float/int | SMC | Confirmed events only | null if absent |
| htf_*_bias, mtf_alignment_score, market_state_code | float/int | MTF | Closed HTF candles only | 0/null |
| strategy_score, direction, condition flags, rr_candidate | float/int | Strategy | Not trade results | null |
| hour_utc, day_of_week, day_of_month, month | int | Time | UTC explicit | — |

Normalization hints are metadata only (`NONE` / `STANDARDIZE` / `MINMAX` / `CATEGORICAL`). **No scalers fitted in Phase 8.**

Full programmatic catalog: `app.ml.feature_schema.feature_catalog()`.
