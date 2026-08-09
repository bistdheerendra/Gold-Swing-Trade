"""Deterministic entry / SL / TP execution helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from app.backtest.config import AmbiguityPolicy, BacktestCostConfig, TpMode
from app.market.schemas import OHLCVBar


@dataclass
class LevelTouch:
    sl_hit: bool
    tp_hit: bool
    ambiguous: bool


def entry_zone_touched(*, bullish: bool, bar: OHLCVBar, low: float, high: float) -> bool:
    """
    Entry triggers when candle range intersects the entry zone.

    BUY/SELL share the same geometric rule:
        bar.low <= entry_high AND bar.high >= entry_low
    """
    if low > high:
        low, high = high, low
    return bar.low <= high and bar.high >= low


def resolve_fill_price(
    *,
    bullish: bool,
    bar: OHLCVBar,
    zone_low: float,
    zone_high: float,
    preferred: float,
    cost: BacktestCostConfig,
) -> float:
    """
    Fill inside intersection of entry zone and candle range.
    Prefer preferred if inside intersection; else clamp to intersection.
    Then apply half-spread + slippage adversely.
    """
    zlo, zhi = (zone_low, zone_high) if zone_low <= zone_high else (zone_high, zone_low)
    ilo = max(zlo, bar.low)
    ihi = min(zhi, bar.high)
    if ilo > ihi:
        # Should not happen if entry_zone_touched; fallback to preferred clamp
        raw = min(max(preferred, bar.low), bar.high)
    elif ilo <= preferred <= ihi:
        raw = preferred
    else:
        raw = min(max(preferred, ilo), ihi)

    half_spread = cost.effective_spread() / 2.0
    slip = cost.effective_slippage()
    if bullish:
        return raw + half_spread + slip
    return raw - half_spread - slip


def apply_exit_costs(
    *,
    bullish: bool,
    price: float,
    cost: BacktestCostConfig,
) -> float:
    half_spread = cost.effective_spread() / 2.0
    slip = cost.effective_slippage()
    if bullish:
        # Selling to exit — adverse
        return price - half_spread - slip
    return price + half_spread + slip


def select_target_price(targets: Sequence[dict], mode: TpMode) -> Optional[float]:
    if not targets:
        return None
    by_label = {str(t.get("label", "")).upper(): float(t["price"]) for t in targets if "price" in t}
    ordered = [float(t["price"]) for t in targets if "price" in t]
    if mode == TpMode.FULL_AT_TP1 or mode == TpMode.TP1_THEN_RUNNER:
        return by_label.get("TP1", ordered[0])
    if mode == TpMode.TP2:
        return by_label.get("TP2", ordered[1] if len(ordered) > 1 else ordered[0])
    if mode == TpMode.TP3:
        return by_label.get("TP3", ordered[-1])
    return ordered[0]


def validate_levels(*, bullish: bool, entry: float, sl: float, tp: float) -> list[str]:
    errs: list[str] = []
    if bullish:
        if sl >= entry:
            errs.append("BUY SL must be below entry")
        if tp <= entry:
            errs.append("BUY TP must be above entry")
    else:
        if sl <= entry:
            errs.append("SELL SL must be above entry")
        if tp >= entry:
            errs.append("SELL TP must be below entry")
    return errs


def check_sl_tp_touch(
    *,
    bullish: bool,
    bar: OHLCVBar,
    sl: float,
    tp: float,
) -> LevelTouch:
    if bullish:
        sl_hit = bar.low <= sl
        tp_hit = bar.high >= tp
    else:
        sl_hit = bar.high >= sl
        tp_hit = bar.low <= tp
    return LevelTouch(sl_hit=sl_hit, tp_hit=tp_hit, ambiguous=sl_hit and tp_hit)


def resolve_exit(
    *,
    bullish: bool,
    bar: OHLCVBar,
    sl: float,
    tp: float,
    policy: AmbiguityPolicy,
    cost: BacktestCostConfig,
) -> Tuple[Optional[str], Optional[float]]:
    """
    Returns (exit_reason, exit_price) or (None, None) if still open.

    CONSERVATIVE: if both SL and TP touched → SL first.
    SKIP: if both touched → AMBIGUOUS_SKIP (caller decides).
    """
    touch = check_sl_tp_touch(bullish=bullish, bar=bar, sl=sl, tp=tp)
    if touch.ambiguous:
        if policy == AmbiguityPolicy.SKIP:
            return "AMBIGUOUS_SKIP", None
        # CONSERVATIVE → SL
        return "SL", apply_exit_costs(bullish=bullish, price=sl, cost=cost)
    if touch.sl_hit:
        return "SL", apply_exit_costs(bullish=bullish, price=sl, cost=cost)
    if touch.tp_hit:
        return "TP", apply_exit_costs(bullish=bullish, price=tp, cost=cost)
    return None, None
