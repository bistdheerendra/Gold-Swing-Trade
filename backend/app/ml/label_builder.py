"""Future-only label construction (may use bars > T; never written into features)."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from app.backtest.config import AmbiguityPolicy, BacktestCostConfig, CostMode
from app.backtest.execution import entry_zone_touched, resolve_exit
from app.market.schemas import OHLCVBar
from app.ml.config import LabelConfig, TripleBarrierConfig
from app.strategy.schemas import SignalDirection, StrategyAnalyzeResult
from app.ta.indicators import atr as compute_atr


class LabelBuilder:
    def __init__(self, config: Optional[LabelConfig] = None) -> None:
        self.config = config or LabelConfig()
        self._atr_cache: Optional[List[Optional[float]]] = None
        self._atr_n_bars: int = -1

    def prime_atr(self, bars: Sequence[OHLCVBar]) -> None:
        """Precompute Wilder ATR for the full entry series (once per build)."""
        tb = self.config.triple_barrier
        self._atr_cache = compute_atr(
            [b.high for b in bars],
            [b.low for b in bars],
            [b.close for b in bars],
            tb.atr_period,
        )
        self._atr_n_bars = len(bars)

    def build(
        self,
        bars: Sequence[OHLCVBar],
        index: int,
        *,
        strategy: Optional[StrategyAnalyzeResult] = None,
    ) -> Dict[str, Optional[float | int | str]]:
        if self.config.labeling_mode == "triple_barrier":
            return self._build_triple_barrier(bars, index)

        labels: Dict[str, Optional[float | int | str]] = {}
        close = bars[index].close
        max_h = max(self.config.horizons) if self.config.horizons else 0

        if self.config.include_forward_returns:
            for h in self.config.horizons:
                labels[f"return_{h}"] = self._forward_return(bars, index, h, close)
            thr = self.config.direction_threshold_pct
            r = labels.get(f"return_{self.config.primary_horizon}")
            if r is None:
                labels["direction"] = None
            elif r > thr:
                labels["direction"] = "UP"
            elif r < -thr:
                labels["direction"] = "DOWN"
            else:
                labels["direction"] = "NEUTRAL"

        if self.config.include_mfe_mae:
            for h in self.config.horizons:
                mfe, mae = self._mfe_mae(bars, index, h, close)
                labels[f"mfe_{h}"] = mfe
                labels[f"mae_{h}"] = mae

        if self.config.include_strategy_outcome:
            outcome, future_r, multi = self._strategy_outcome(bars, index, strategy)
            labels["strategy_outcome"] = outcome
            labels["future_R"] = future_r
            if self.config.include_multiclass:
                labels["multiclass_outcome"] = multi

        if index + max_h >= len(bars):
            labels["_truncated"] = 1
        return labels

    def _build_triple_barrier(
        self, bars: Sequence[OHLCVBar], index: int
    ) -> Dict[str, Optional[float | int | str]]:
        tb = self.config.triple_barrier
        n = int(tb.horizon_bars)
        labels: Dict[str, Optional[float | int | str]] = {
            "tb_horizon": n,
            "tb_atr_mult": float(tb.atr_mult),
        }
        close = bars[index].close
        if self.config.include_forward_returns:
            labels[f"return_{n}"] = self._forward_return(bars, index, n, close)
        if self.config.include_mfe_mae:
            mfe, mae = self._mfe_mae(bars, index, n, close)
            labels[f"mfe_{n}"] = mfe
            labels[f"mae_{n}"] = mae

        atr_series = self._atr_cache if self._atr_n_bars == len(bars) else None
        direction, atr_t = triple_barrier_direction(
            bars, index, tb, atr_series=atr_series
        )
        labels["direction"] = direction
        labels["tb_atr"] = atr_t
        if direction is None:
            labels["_truncated"] = 1
        return labels

    def _forward_return(
        self, bars: Sequence[OHLCVBar], index: int, horizon: int, close: float
    ) -> Optional[float]:
        j = index + horizon
        if j >= len(bars) or close == 0:
            return None
        return (bars[j].close - close) / close

    def _mfe_mae(
        self, bars: Sequence[OHLCVBar], index: int, horizon: int, close: float
    ) -> tuple[Optional[float], Optional[float]]:
        end = min(len(bars) - 1, index + horizon)
        if end <= index or close == 0:
            return None, None
        window = bars[index + 1 : end + 1]
        if not window:
            return None, None
        max_high = max(b.high for b in window)
        min_low = min(b.low for b in window)
        mfe = (max_high - close) / close
        mae = (close - min_low) / close
        return mfe, mae

    def _strategy_outcome(
        self,
        bars: Sequence[OHLCVBar],
        index: int,
        strategy: Optional[StrategyAnalyzeResult],
    ) -> tuple[str, Optional[float], str]:
        """
        Uses Phase 7 execution assumptions (zone entry, CONSERVATIVE ambiguity).
        """
        if strategy is None or strategy.signal in (
            SignalDirection.WAIT,
            SignalDirection.NO_TRADE,
        ):
            return "NO_SETUP", None, "NO_SETUP"

        if strategy.entry is None or strategy.stop_loss is None or not strategy.targets:
            return "NO_ENTRY", None, "NO_SETUP"

        bullish = strategy.signal == SignalDirection.BUY
        entry_low = strategy.entry.low
        entry_high = strategy.entry.high
        preferred = strategy.entry.preferred
        sl = strategy.stop_loss
        tp = float(strategy.targets[0].price)
        cost = BacktestCostConfig(mode=CostMode.ZERO_COST)
        max_age = 12

        entry_price: Optional[float] = None
        entry_i: Optional[int] = None
        for j in range(index, min(len(bars), index + max_age + 1)):
            bar = bars[j]
            if not entry_zone_touched(
                bullish=bullish, bar=bar, low=entry_low, high=entry_high
            ):
                continue
            ilo = max(entry_low, bar.low)
            ihi = min(entry_high, bar.high)
            if ilo > ihi:
                continue
            entry_price = preferred if ilo <= preferred <= ihi else min(max(preferred, ilo), ihi)
            entry_i = j
            break

        if entry_price is None or entry_i is None:
            return "NO_ENTRY", None, "NO_SETUP"

        risk = abs(entry_price - sl)
        if risk <= 0:
            return "NO_ENTRY", None, "NO_SETUP"

        for j in range(entry_i, len(bars)):
            bar = bars[j]
            reason, _ = resolve_exit(
                bullish=bullish,
                bar=bar,
                sl=sl,
                tp=tp,
                policy=AmbiguityPolicy.CONSERVATIVE,
                cost=cost,
            )
            if reason is None:
                continue
            if reason == "AMBIGUOUS_SKIP":
                return "NO_ENTRY", None, "NO_SETUP"
            if reason == "SL":
                r = -1.0
                multi = "BUY_LOSS" if bullish else "SELL_LOSS"
                return "LOSS", r, multi
            reward = abs(tp - entry_price)
            r = reward / risk
            multi = "BUY_WIN" if bullish else "SELL_WIN"
            return "WIN", r, multi

        return "NO_ENTRY", None, "NO_SETUP"


def triple_barrier_direction(
    bars: Sequence[OHLCVBar],
    index: int,
    config: Optional[TripleBarrierConfig] = None,
    *,
    atr_series: Optional[Sequence[Optional[float]]] = None,
) -> tuple[Optional[str], Optional[float]]:
    """
    ATR-normalized triple-barrier label at bar `index`.

    Features must not call this with future data for *feature* construction;
    labels intentionally inspect bars after `index`.
    """
    tb = config or TripleBarrierConfig()
    n = int(tb.horizon_bars)
    if index < 0 or index + n >= len(bars):
        return None, None

    if atr_series is None:
        highs = [b.high for b in bars]
        lows = [b.low for b in bars]
        closes = [b.close for b in bars]
        atr_series = compute_atr(highs, lows, closes, tb.atr_period)

    atr_t = atr_series[index] if index < len(atr_series) else None
    if atr_t is None or atr_t <= 0:
        return None, atr_t

    close = float(bars[index].close)
    upper = close + float(tb.atr_mult) * float(atr_t)
    lower = close - float(tb.atr_mult) * float(atr_t)

    for j in range(index + 1, index + n + 1):
        bar = bars[j]
        hit_up = bar.high >= upper
        hit_dn = bar.low <= lower
        if hit_up and hit_dn:
            return tb.same_bar_both, float(atr_t)
        if hit_up:
            return "UP", float(atr_t)
        if hit_dn:
            return "DOWN", float(atr_t)
    return tb.vertical_label, float(atr_t)
