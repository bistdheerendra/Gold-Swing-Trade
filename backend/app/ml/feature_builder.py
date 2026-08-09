"""Causal feature extraction from TA / SMC / MTF / Strategy / bar."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Sequence

from app.market.schemas import OHLCVBar, ensure_utc
from app.ml.config import FeatureConfig
from app.mtf.schemas import BiasLabel, MultiTimeframeResult, MtfState
from app.smc.schemas import (
    DealingZone,
    FvgLifecycle,
    SmcAnalysisResult,
    SmcDirection,
)
from app.strategy.schemas import SignalDirection, StrategyAnalyzeResult
from app.ta.schemas import TechnicalAnalysisResult


def _bias_num(label: str | BiasLabel | SmcDirection | None) -> int:
    if label is None:
        return 0
    v = label.value if hasattr(label, "value") else str(label)
    u = v.upper()
    if u in ("BULLISH", "BUY", "UP", "STRONG_BULLISH"):
        return 1
    if u in ("BEARISH", "SELL", "DOWN", "STRONG_BEARISH"):
        return -1
    return 0


def _pct(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    return (num / den) * 100.0


def _slope(series: Sequence[Optional[float]], idx: int, look: int = 3) -> Optional[float]:
    if idx < look:
        return None
    a = series[idx - look] if idx - look < len(series) else None
    b = series[idx] if idx < len(series) else None
    if a is None or b is None:
        return None
    return b - a


def _atr_percentile(atr_series: Sequence[Optional[float]], idx: int, lookback: int) -> Optional[float]:
    cur = atr_series[idx] if idx < len(atr_series) else None
    if cur is None:
        return None
    start = max(0, idx - lookback + 1)
    window = [float(v) for v in atr_series[start : idx + 1] if v is not None]
    if len(window) < 5:
        return None
    window_sorted = sorted(window)
    # rank of current among historical incl current
    rank = sum(1 for v in window_sorted if v <= cur)
    return rank / len(window_sorted)


_STATE_CODE = {
    "TRENDING": 4,
    "PULLBACK": 3,
    "REVERSAL_RISK": 2,
    "RANGING": 1,
    "CONFLICT": -1,
    "NEUTRAL": 0,
}


class FeatureBuilder:
    def __init__(self, config: Optional[FeatureConfig] = None) -> None:
        self.config = config or FeatureConfig()

    def build(
        self,
        *,
        bar: OHLCVBar,
        index: int,
        ta: Optional[TechnicalAnalysisResult],
        smc: Optional[SmcAnalysisResult],
        mtf: Optional[MultiTimeframeResult],
        strategy: Optional[StrategyAnalyzeResult],
    ) -> Dict[str, Optional[float | int | str]]:
        feats: Dict[str, Optional[float | int | str]] = {}
        if self.config.include_price_action:
            feats.update(self._price_action(bar))
        if self.config.include_ta and ta is not None:
            feats.update(self._ta(ta, index))
        if self.config.include_smc and smc is not None:
            feats.update(self._smc(smc, bar.close, index))
        if self.config.include_mtf and mtf is not None:
            feats.update(self._mtf(mtf))
        if self.config.include_strategy and strategy is not None:
            feats.update(self._strategy(strategy))
        if self.config.include_time:
            feats.update(self._time(bar.timestamp))
        return feats

    def _price_action(self, bar: OHLCVBar) -> Dict[str, Optional[float | int]]:
        rng = bar.high - bar.low
        body = abs(bar.close - bar.open)
        upper = bar.high - max(bar.open, bar.close)
        lower = min(bar.open, bar.close) - bar.low
        close_pos = ((bar.close - bar.low) / rng) if rng > 0 else 0.5
        return {
            "body_size_pct": _pct(body, bar.close),
            "upper_wick_pct": _pct(upper, bar.close),
            "lower_wick_pct": _pct(lower, bar.close),
            "range_pct": _pct(rng, bar.close),
            "close_position_in_range": close_pos,
            "bullish_candle": 1 if bar.close > bar.open else 0,
            "bearish_candle": 1 if bar.close < bar.open else 0,
        }

    def _ta(self, ta: TechnicalAnalysisResult, index: int) -> Dict[str, Optional[float | int]]:
        latest = ta.latest
        close = None
        # prefer series close via ema distance needing close — use dealing from price via ema
        # Latest indicators are at as_of; reconstruct close from distance if needed
        # We pass bar.close separately in build — store via ema if available
        price = None
        for candidate in (latest.ema_20, latest.ema_50, latest.bb_mid):
            if candidate is not None:
                # approximate: use ema and distance later; need actual close from caller
                break
        # Use series if available
        series = ta.series or {}
        closes = series.get("close")  # may not exist
        # TA engine may not expose close series — use ema20 as anchor only for ratios between emas
        # Feature builder receives bar in build(); recompute distances using bar is better.
        # This method is called from build with bar available — refactor: pass close
        return {}  # filled by _ta_with_close

    def build_with_close(
        self,
        *,
        bar: OHLCVBar,
        index: int,
        ta: Optional[TechnicalAnalysisResult],
        smc: Optional[SmcAnalysisResult],
        mtf: Optional[MultiTimeframeResult],
        strategy: Optional[StrategyAnalyzeResult],
    ) -> Dict[str, Optional[float | int | str]]:
        feats = self.build(bar=bar, index=index, ta=None, smc=smc, mtf=mtf, strategy=strategy)
        # rebuild price + ta properly
        out: Dict[str, Optional[float | int | str]] = {}
        if self.config.include_price_action:
            out.update(self._price_action(bar))
        if self.config.include_ta and ta is not None:
            out.update(self._ta_with_close(ta, bar.close, index))
        if self.config.include_volatility and ta is not None:
            out.update(self._volatility(ta, bar.close, index))
        if self.config.include_smc and smc is not None:
            out.update(self._smc(smc, bar.close, index))
        if self.config.include_mtf and mtf is not None:
            out.update(self._mtf(mtf))
        if self.config.include_strategy and strategy is not None:
            out.update(self._strategy(strategy))
        if self.config.include_time:
            out.update(self._time(bar.timestamp))
        return out

    def _ta_with_close(
        self, ta: TechnicalAnalysisResult, close: float, index: int
    ) -> Dict[str, Optional[float | int]]:
        L = ta.latest
        series = ta.series or {}
        out: Dict[str, Optional[float | int]] = {}
        for p, val in (
            (20, L.ema_20),
            (50, L.ema_50),
            (100, L.ema_100),
            (200, L.ema_200),
        ):
            out[f"ema{p}_distance_pct"] = _pct(close - val, close) if val is not None else None
            key = f"ema_{p}"
            s = series.get(key)
            out[f"ema{p}_slope"] = _slope(s, index) if s else None

        def ratio(a: Optional[float], b: Optional[float]) -> Optional[float]:
            if a is None or b is None or close == 0:
                return None
            return (a - b) / close

        out["ema20_vs_50"] = ratio(L.ema_20, L.ema_50)
        out["ema50_vs_100"] = ratio(L.ema_50, L.ema_100)
        out["ema100_vs_200"] = ratio(L.ema_100, L.ema_200)
        emas = [L.ema_20, L.ema_50, L.ema_100, L.ema_200]
        if all(v is not None for v in emas):
            if emas[0] > emas[1] > emas[2] > emas[3]:  # type: ignore[operator]
                out["ema_alignment"] = 1
            elif emas[0] < emas[1] < emas[2] < emas[3]:  # type: ignore[operator]
                out["ema_alignment"] = -1
            else:
                out["ema_alignment"] = 0
        else:
            out["ema_alignment"] = None

        out["rsi"] = L.rsi
        out["rsi_distance_from_50"] = (L.rsi - 50.0) if L.rsi is not None else None
        out["macd"] = L.macd
        out["macd_signal"] = L.macd_signal
        out["macd_histogram"] = L.macd_histogram
        hist = series.get("macd_histogram")
        out["macd_histogram_slope"] = _slope(hist, index) if hist else None
        out["adx"] = L.adx
        out["atr"] = L.atr
        out["atr_pct"] = _pct(L.atr, close)
        if L.bb_upper is not None and L.bb_lower is not None and L.bb_upper != L.bb_lower:
            out["bb_position"] = (close - L.bb_lower) / (L.bb_upper - L.bb_lower)
        else:
            out["bb_position"] = None
        if L.bb_mid and L.bb_upper is not None and L.bb_lower is not None:
            out["bb_width"] = (L.bb_upper - L.bb_lower) / L.bb_mid if L.bb_mid else None
        else:
            out["bb_width"] = None
        return out

    def _volatility(
        self, ta: TechnicalAnalysisResult, close: float, index: int
    ) -> Dict[str, Optional[float]]:
        series = ta.series or {}
        atr_s = series.get("atr")
        out: Dict[str, Optional[float]] = {
            "atr": ta.latest.atr,
            "atr_pct": _pct(ta.latest.atr, close),
        }
        if atr_s:
            out["atr_percentile"] = _atr_percentile(
                atr_s, index, self.config.atr_percentile_lookback
            )
        else:
            out["atr_percentile"] = None
        return out

    def _smc(
        self, smc: SmcAnalysisResult, close: float, index: int
    ) -> Dict[str, Optional[float | int]]:
        out: Dict[str, Optional[float | int]] = {
            "structure_bias": _bias_num(smc.structure.bias),
            "last_bos_direction": None,
            "last_bos_age": None,
            "last_choch_direction": None,
            "last_choch_age": None,
            "bullish_fvg_present": 0,
            "bearish_fvg_present": 0,
            "nearest_bullish_fvg_distance_pct": None,
            "nearest_bearish_fvg_distance_pct": None,
            "bullish_ob_present": 0,
            "bearish_ob_present": 0,
            "nearest_bullish_ob_distance_pct": None,
            "nearest_bearish_ob_distance_pct": None,
            "demand_present": 0,
            "supply_present": 0,
            "buy_side_liquidity_distance_pct": None,
            "sell_side_liquidity_distance_pct": None,
            "liquidity_sweep_direction": None,
            "liquidity_sweep_age": None,
            "premium_discount_state": 0,
            "distance_from_equilibrium_pct": None,
        }
        # Only confirmed events
        bos = [e for e in smc.bos if e.confirm_index <= index]
        choch = [e for e in smc.choch if e.confirm_index <= index]
        if bos:
            last = bos[-1]
            out["last_bos_direction"] = _bias_num(last.direction)
            out["last_bos_age"] = index - last.confirm_index
        if choch:
            last = choch[-1]
            out["last_choch_direction"] = _bias_num(last.direction)
            out["last_choch_age"] = index - last.confirm_index

        def fvg_ok(f) -> bool:
            return (
                f.confirm_index <= index
                and f.valid
                and not f.filled
                and f.lifecycle
                in (FvgLifecycle.CREATED, FvgLifecycle.ACTIVE, FvgLifecycle.PARTIALLY_FILLED)
            )

        bull_fvgs = [f for f in smc.fvg if fvg_ok(f) and f.direction == SmcDirection.BULLISH]
        bear_fvgs = [f for f in smc.fvg if fvg_ok(f) and f.direction == SmcDirection.BEARISH]
        out["bullish_fvg_present"] = 1 if bull_fvgs else 0
        out["bearish_fvg_present"] = 1 if bear_fvgs else 0
        if bull_fvgs:
            mid = ((bull_fvgs[-1].low or close) + (bull_fvgs[-1].high or close)) / 2
            out["nearest_bullish_fvg_distance_pct"] = _pct(close - mid, close)
        if bear_fvgs:
            mid = ((bear_fvgs[-1].low or close) + (bear_fvgs[-1].high or close)) / 2
            out["nearest_bearish_fvg_distance_pct"] = _pct(close - mid, close)

        bull_ob = [
            z
            for z in smc.order_blocks
            if z.confirm_index <= index and z.valid and not z.mitigated and z.direction == SmcDirection.BULLISH
        ]
        bear_ob = [
            z
            for z in smc.order_blocks
            if z.confirm_index <= index and z.valid and not z.mitigated and z.direction == SmcDirection.BEARISH
        ]
        out["bullish_ob_present"] = 1 if bull_ob else 0
        out["bearish_ob_present"] = 1 if bear_ob else 0
        if bull_ob:
            mid = ((bull_ob[-1].low or close) + (bull_ob[-1].high or close)) / 2
            out["nearest_bullish_ob_distance_pct"] = _pct(close - mid, close)
        if bear_ob:
            mid = ((bear_ob[-1].low or close) + (bear_ob[-1].high or close)) / 2
            out["nearest_bearish_ob_distance_pct"] = _pct(close - mid, close)

        out["demand_present"] = 1 if any(
            z.confirm_index <= index and z.valid and not z.mitigated for z in smc.demand_zones
        ) else 0
        out["supply_present"] = 1 if any(
            z.confirm_index <= index and z.valid and not z.mitigated for z in smc.supply_zones
        ) else 0

        for pool in smc.liquidity:
            if pool.confirm_index > index or not pool.valid:
                continue
            px = pool.price or pool.high or pool.low
            if px is None:
                continue
            dist = _pct(px - close, close)
            if pool.type.value == "buy_side_liquidity":
                out["buy_side_liquidity_distance_pct"] = dist
            elif pool.type.value == "sell_side_liquidity":
                out["sell_side_liquidity_distance_pct"] = dist

        sweeps = [s for s in smc.liquidity_sweeps if s.confirm_index <= index and s.valid]
        if sweeps:
            s = sweeps[-1]
            out["liquidity_sweep_direction"] = _bias_num(s.direction)
            out["liquidity_sweep_age"] = index - s.confirm_index

        zone = smc.dealing_range.zone
        if zone == DealingZone.PREMIUM:
            out["premium_discount_state"] = 1
        elif zone == DealingZone.DISCOUNT:
            out["premium_discount_state"] = -1
        else:
            out["premium_discount_state"] = 0
        if smc.dealing_range.equilibrium:
            out["distance_from_equilibrium_pct"] = _pct(
                close - smc.dealing_range.equilibrium, close
            )
        return out

    def _mtf(self, mtf: MultiTimeframeResult) -> Dict[str, Optional[float | int]]:
        tfs = mtf.timeframes
        return {
            "htf_1d_bias": _bias_num(tfs["1d"].trend) if "1d" in tfs else 0,
            "htf_4h_bias": _bias_num(tfs["4h"].trend) if "4h" in tfs else 0,
            "htf_1h_bias": _bias_num(tfs["1h"].trend) if "1h" in tfs else 0,
            "htf_30m_bias": _bias_num(tfs["30m"].trend) if "30m" in tfs else 0,
            "entry_15m_bias": _bias_num(tfs["15m"].trend) if "15m" in tfs else 0,
            "mtf_alignment_score": mtf.alignment_score,
            "higher_timeframe_bias": _bias_num(mtf.higher_timeframe_bias),
            "setup_bias": _bias_num(mtf.setup_bias),
            "entry_bias": _bias_num(mtf.entry_bias),
            "market_state_code": _STATE_CODE.get(mtf.state.value, 0),
        }

    def _strategy(self, s: StrategyAnalyzeResult) -> Dict[str, Optional[float | int]]:
        cond = {c.key: c for c in s.conditions}
        def flag(key: str) -> int:
            c = cond.get(key)
            return 1 if c and c.met else 0

        dir_map = {
            SignalDirection.BUY: 1,
            SignalDirection.SELL: -1,
            SignalDirection.WAIT: 0,
            SignalDirection.NO_TRADE: 0,
        }
        vol = {"NORMAL": 0, "HIGH": 1, "EXTREME": 2, "UNKNOWN": -1}.get(s.volatility.value, -1)
        return {
            "strategy_score": s.score,
            "strategy_direction": dir_map.get(s.signal, 0),
            "strategy_state_code": dir_map.get(s.signal, 0),
            "cond_htf_alignment": flag("higher_tf_bias") or flag("structure_4h"),
            "cond_structure_confirmation": flag("bos_choch"),
            "cond_liquidity_confirmation": flag("liquidity_sweep"),
            "cond_ob_confirmation": flag("ob_demand_supply"),
            "cond_fvg_confirmation": flag("fvg"),
            "cond_entry_confirmation": flag("entry_15m"),
            "rr_candidate": s.primary_rr,
            "volatility_filter_state": vol,
        }

    def _time(self, ts: datetime) -> Dict[str, int]:
        t = ensure_utc(ts)
        return {
            "hour_utc": t.hour,
            "day_of_week": t.weekday(),
            "day_of_month": t.day,
            "month": t.month,
        }
