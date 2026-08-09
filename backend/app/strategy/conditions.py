"""Deterministic condition evaluators for BUY/SELL scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from app.mtf.schemas import BiasLabel, MultiTimeframeResult, MtfState
from app.smc.schemas import (
    DealingZone,
    FvgLifecycle,
    SmcAnalysisResult,
    SmcDirection,
    SweepEvent,
)
from app.strategy.config import ScoreWeights, StrategyConfig
from app.strategy.schemas import ConditionScore


@dataclass
class DirectionalContext:
    """SMC snapshots used for one trade direction evaluation."""

    smc_4h: Optional[SmcAnalysisResult]
    smc_1h: Optional[SmcAnalysisResult]
    smc_15m: Optional[SmcAnalysisResult]
    mtf: MultiTimeframeResult
    as_of_index_15m: int


def score_buy_conditions(
    ctx: DirectionalContext,
    config: StrategyConfig,
) -> List[ConditionScore]:
    return _score_direction(ctx, config, bullish=True)


def score_sell_conditions(
    ctx: DirectionalContext,
    config: StrategyConfig,
) -> List[ConditionScore]:
    return _score_direction(ctx, config, bullish=False)


def _score_direction(
    ctx: DirectionalContext,
    config: StrategyConfig,
    *,
    bullish: bool,
) -> List[ConditionScore]:
    w = config.score_weights
    want = SmcDirection.BULLISH if bullish else SmcDirection.BEARISH
    want_bias = BiasLabel.BULLISH if bullish else BiasLabel.BEARISH
    opposite_bias = BiasLabel.BEARISH if bullish else BiasLabel.BULLISH

    out: List[ConditionScore] = []

    # Higher TF bias (1D + 4H blend already in mtf.higher_timeframe_bias)
    htf = ctx.mtf.higher_timeframe_bias
    if htf == want_bias:
        pts, met, detail = w.higher_tf_bias, True, f"HTF bias {htf.value}"
    elif htf == BiasLabel.NEUTRAL:
        pts, met, detail = w.higher_tf_bias * 0.5, True, f"HTF bias NEUTRAL (partial)"
    else:
        pts, met, detail = 0.0, False, f"HTF bias opposing ({htf.value})"
    out.append(_c("higher_tf_bias", "Higher TF Bias", met, pts, w.higher_tf_bias, detail))

    # 4H structure
    s4 = ctx.mtf.structure.bias if ctx.mtf.structure else BiasLabel.NEUTRAL
    smc4_bias = (
        ctx.smc_4h.structure.bias if ctx.smc_4h else SmcDirection.NEUTRAL
    )
    structure_ok = s4 == want_bias or smc4_bias == want
    if structure_ok:
        pts, met, detail = w.structure_4h, True, f"4H structure {s4.value} / SMC {smc4_bias.value}"
    elif s4 == BiasLabel.NEUTRAL and smc4_bias == SmcDirection.NEUTRAL:
        pts, met, detail = w.structure_4h * 0.35, False, "4H structure neutral"
    else:
        pts, met, detail = 0.0, False, f"4H structure {s4.value}"
    out.append(_c("structure_4h", "4H Structure", met, pts, w.structure_4h, detail))

    # 1H setup — allow pullback from bullish HTF
    setup = ctx.mtf.setup_bias
    state = ctx.mtf.state
    pullback_ok = state == MtfState.PULLBACK and htf == want_bias
    if setup == want_bias:
        pts, met, detail = w.setup_1h, True, f"1H setup {setup.value}"
    elif pullback_ok:
        pts, met, detail = w.setup_1h * 0.7, True, f"1H pullback vs HTF {htf.value}"
    elif setup == BiasLabel.NEUTRAL:
        pts, met, detail = w.setup_1h * 0.4, False, "1H setup neutral"
    else:
        pts, met, detail = 0.0, False, f"1H setup {setup.value}"
    out.append(_c("setup_1h", "1H Setup", met, pts, w.setup_1h, detail))

    # Liquidity sweep (prefer sell-side for BUY, buy-side for SELL)
    sweep = _recent_sweep(ctx.smc_1h or ctx.smc_15m, want, config)
    if sweep is not None:
        pts, met, detail = (
            w.liquidity_sweep,
            True,
            f"Liquidity sweep @ {sweep.liquidity_level:.2f}",
        )
    else:
        pts, met, detail = 0.0, False, "No recent directional liquidity sweep"
    out.append(
        _c("liquidity_sweep", "Liquidity Sweep", met, pts, w.liquidity_sweep, detail)
    )

    # BOS / CHoCH
    break_ev = _recent_break(ctx.smc_1h, want, config)
    if break_ev is None and ctx.smc_15m:
        break_ev = _recent_break(ctx.smc_15m, want, config)
    if break_ev is not None:
        kind = break_ev.type.value.upper()
        pts, met, detail = w.bos_choch, True, f"{kind} {break_ev.direction.value}"
    else:
        pts, met, detail = 0.0, False, "No recent directional BOS/CHoCH"
    out.append(_c("bos_choch", "BOS/CHoCH", met, pts, w.bos_choch, detail))

    # OB / demand / supply
    zone_ok, zone_detail = _zone_location(ctx.smc_1h or ctx.smc_15m, bullish=bullish)
    pts = w.ob_demand_supply if zone_ok else 0.0
    out.append(
        _c(
            "ob_demand_supply",
            "OB/Demand/Supply",
            zone_ok,
            pts,
            w.ob_demand_supply,
            zone_detail,
        )
    )

    # FVG
    fvg_ok, fvg_detail = _active_fvg(ctx.smc_1h or ctx.smc_15m, bullish=bullish)
    pts = w.fvg if fvg_ok else 0.0
    out.append(_c("fvg", "FVG", fvg_ok, pts, w.fvg, fvg_detail))

    # Premium / discount
    zone = DealingZone.UNKNOWN
    src = ctx.smc_1h or ctx.smc_4h
    if src:
        zone = src.dealing_range.zone
    if bullish and zone == DealingZone.DISCOUNT:
        pts, met, detail = w.premium_discount, True, "Price in discount"
    elif (not bullish) and zone == DealingZone.PREMIUM:
        pts, met, detail = w.premium_discount, True, "Price in premium"
    elif zone == DealingZone.EQUILIBRIUM:
        pts, met, detail = w.premium_discount * 0.4, False, "Price near equilibrium"
    else:
        pts, met, detail = 0.0, False, f"Dealing zone {zone.value}"
    out.append(
        _c("premium_discount", "Premium/Discount", met, pts, w.premium_discount, detail)
    )

    # 15M confirmation
    entry = ctx.mtf.entry_bias
    entry_break = _recent_break(ctx.smc_15m, want, config, bars=config.entry_confirm_bars)
    entry_sweep = _recent_sweep(ctx.smc_15m, want, config, bars=config.entry_confirm_bars)
    if entry == want_bias or entry_break is not None or entry_sweep is not None:
        pts, met, detail = w.entry_15m, True, _entry_detail(entry, entry_break, entry_sweep)
    elif entry == opposite_bias:
        pts, met, detail = 0.0, False, f"15M opposing ({entry.value})"
    else:
        pts, met, detail = 0.0, False, "15M confirmation incomplete"
    out.append(_c("entry_15m", "15M Confirmation", met, pts, w.entry_15m, detail))

    return out


def detect_strong_conflict(ctx: DirectionalContext, *, bullish: bool) -> Optional[str]:
    """
    Strong structural conflict that should force NO_TRADE rather than WAIT.
    Mild conflicts (e.g. missing 15M) are left to scoring → WAIT.
    """
    want = BiasLabel.BULLISH if bullish else BiasLabel.BEARISH
    opp = BiasLabel.BEARISH if bullish else BiasLabel.BULLISH
    htf = ctx.mtf.higher_timeframe_bias
    setup = ctx.mtf.setup_bias
    entry = ctx.mtf.entry_bias
    state = ctx.mtf.state

    if state == MtfState.CONFLICT and htf == opp:
        return "Major MTF conflict against trade direction"
    if htf == opp and setup == opp and entry == opp:
        return "All layers oppose proposed direction"
    if state == MtfState.REVERSAL_RISK and setup == opp and entry == opp:
        return "Reversal risk with opposing setup and entry"
    # HTF agrees but setup+entry strongly against with ranging — still WAIT usually
    if htf == want and setup == opp and entry == opp and state == MtfState.REVERSAL_RISK:
        return "Setup and entry reversing against HTF"
    return None


def _c(
    key: str,
    label: str,
    met: bool,
    points: float,
    max_points: float,
    detail: str,
) -> ConditionScore:
    return ConditionScore(
        key=key,
        label=label,
        met=met,
        points=round(points, 2),
        max_points=max_points,
        detail=detail,
    )


def _recent_sweep(
    smc: Optional[SmcAnalysisResult],
    want: SmcDirection,
    config: StrategyConfig,
    bars: Optional[int] = None,
) -> Optional[SweepEvent]:
    if smc is None:
        return None
    lookback = bars if bars is not None else config.recent_sweep_bars
    cutoff = max(0, smc.as_of_index - lookback)
    candidates = [
        s
        for s in smc.liquidity_sweeps
        if s.valid
        and s.direction == want
        and s.confirm_index <= smc.as_of_index
        and s.confirm_index >= cutoff
    ]
    return candidates[-1] if candidates else None


def _recent_break(
    smc: Optional[SmcAnalysisResult],
    want: SmcDirection,
    config: StrategyConfig,
    bars: Optional[int] = None,
):
    if smc is None:
        return None
    lookback = bars if bars is not None else config.recent_break_bars
    cutoff = max(0, smc.as_of_index - lookback)
    events = list(smc.bos) + list(smc.choch)
    candidates = [
        e
        for e in events
        if e.valid
        and e.direction == want
        and e.confirm_index <= smc.as_of_index
        and e.confirm_index >= cutoff
    ]
    return candidates[-1] if candidates else None


def _zone_location(
    smc: Optional[SmcAnalysisResult], *, bullish: bool
) -> tuple[bool, str]:
    if smc is None:
        return False, "No SMC zone data"
    price = smc.dealing_range.current_price
    if price is None and smc.as_of_index >= 0:
        # dealing range usually has current_price; fallback false
        pass
    zones = smc.demand_zones if bullish else smc.supply_zones
    obs = [z for z in smc.order_blocks if z.valid and not z.mitigated]
    obs = [z for z in obs if z.direction == (SmcDirection.BULLISH if bullish else SmcDirection.BEARISH)]
    active_zones = [z for z in zones if z.valid and not z.mitigated]
    pool = active_zones + obs
    if not pool:
        return False, "No active demand/supply/OB"
    if price is None:
        return True, f"Active {'demand' if bullish else 'supply'}/OB present"
    for z in reversed(pool):
        lo = z.low if z.low is not None else z.price
        hi = z.high if z.high is not None else z.price
        if lo is None or hi is None:
            continue
        # Near zone: within zone or within 0.15% of edges
        pad = abs(hi - lo) * 0.25 + abs(price) * 0.0005
        if lo - pad <= price <= hi + pad:
            return True, f"Price near {'demand/OB' if bullish else 'supply/OB'} [{lo:.2f}-{hi:.2f}]"
    return False, "Price not near active zone"


def _active_fvg(
    smc: Optional[SmcAnalysisResult], *, bullish: bool
) -> tuple[bool, str]:
    if smc is None:
        return False, "No FVG data"
    want_type = "bullish_fvg" if bullish else "bearish_fvg"
    want_dir = SmcDirection.BULLISH if bullish else SmcDirection.BEARISH
    active = [
        f
        for f in smc.fvg
        if f.valid
        and not f.filled
        and f.direction == want_dir
        and f.lifecycle
        in (FvgLifecycle.CREATED, FvgLifecycle.ACTIVE, FvgLifecycle.PARTIALLY_FILLED)
        and f.confirm_index <= smc.as_of_index
    ]
    if not active:
        return False, f"No active {want_type}"
    f = active[-1]
    return True, f"Active {want_type} [{f.low}-{f.high}]"


def _entry_detail(entry: BiasLabel, break_ev, sweep) -> str:
    parts = [f"15M bias {entry.value}"]
    if break_ev is not None:
        parts.append(f"{break_ev.type.value} confirmed")
    if sweep is not None:
        parts.append("liquidity sweep reclaim")
    return "; ".join(parts)


def total_score(conditions: Sequence[ConditionScore], weights: ScoreWeights) -> int:
    raw = sum(c.points for c in conditions)
    tot = weights.total() or 100.0
    # Normalize to 0..100 if weights don't sum to 100
    scaled = (raw / tot) * 100.0
    return int(round(max(0.0, min(100.0, scaled))))
