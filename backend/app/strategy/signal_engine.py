"""Entry zone, structural SL, TP candidates, RR validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from app.market.schemas import OHLCVBar
from app.smc.schemas import (
    FvgLifecycle,
    SmcAnalysisResult,
    SmcDirection,
    ZoneEvent,
)
from app.strategy.config import StrategyConfig
from app.strategy.schemas import EntryZone, TakeProfitLevel


@dataclass
class LevelsResult:
    entry: Optional[EntryZone]
    stop_loss: Optional[float]
    targets: List[TakeProfitLevel]
    primary_rr: Optional[float]
    errors: List[str]
    warnings: List[str]


def compute_levels(
    *,
    bullish: bool,
    bars_15m: Sequence[OHLCVBar],
    smc_1h: Optional[SmcAnalysisResult],
    smc_15m: Optional[SmcAnalysisResult],
    atr: Optional[float],
    config: StrategyConfig,
) -> LevelsResult:
    errors: List[str] = []
    warnings: List[str] = []
    smc = smc_1h or smc_15m
    if not bars_15m:
        return LevelsResult(None, None, [], None, ["No entry bars"], [])

    price = float(bars_15m[-1].close)
    atr_v = float(atr) if atr and atr > 0 else abs(price) * 0.001
    buffer = config.sl_buffer + atr_v * config.sl_atr_buffer_mult
    max_dist = atr_v * max(0.5, float(config.max_entry_distance_atr))

    entry = _entry_zone(
        bullish=bullish,
        price=price,
        smc=smc,
        smc_15m=smc_15m,
        atr=atr_v,
        max_distance=max_dist,
    )
    if entry is None:
        errors.append(
            "No fresh entry zone near spot — stale OB/FVG left behind; "
            "wait for reclaim or new setup"
        )
        return LevelsResult(None, None, [], None, errors, warnings)

    sl = _stop_loss(
        bullish=bullish,
        price=price,
        entry=entry,
        smc=smc,
        smc_15m=smc_15m,
        buffer=buffer,
        max_distance=max_dist,
    )
    if sl is None:
        errors.append("Missing structural stop loss")

    targets: List[TakeProfitLevel] = []
    primary_rr: Optional[float] = None
    if entry is not None and sl is not None:
        pref = entry.preferred
        risk = abs(pref - sl)
        if risk <= 0:
            errors.append("Invalid risk distance (entry == SL)")
        else:
            # Side checks — SL must respect entry geometry, not only last close
            if bullish and sl >= pref:
                errors.append("BUY SL must be below entry")
            if (not bullish) and sl <= pref:
                errors.append("SELL SL must be above entry")

            raw_tps = _candidate_targets(
                bullish=bullish,
                entry=pref,
                smc=smc,
                smc_15m=smc_15m,
            )
            # Filter opposing structure / wrong side / already-passed by spot
            filtered: List[float] = []
            for tp in raw_tps:
                if bullish and tp <= pref:
                    continue
                if (not bullish) and tp >= pref:
                    continue
                if bullish and tp <= sl:
                    continue
                if (not bullish) and tp >= sl:
                    continue
                # Actionable vs live spot: BUY TP above market, SELL TP below market
                if bullish and tp <= price:
                    continue
                if (not bullish) and tp >= price:
                    continue
                filtered.append(tp)

            # Synthetic TP only if still beyond live spot
            if not filtered:
                rr_dist = risk * config.min_rr
                synthetic = pref + rr_dist if bullish else pref - rr_dist
                if (bullish and synthetic > price) or ((not bullish) and synthetic < price):
                    filtered.append(synthetic)
                    warnings.append(
                        "No opposing liquidity/swing TP — used min-RR synthetic TP1"
                    )
                else:
                    errors.append(
                        "All targets already reached/passed by spot — setup is stale"
                    )

            if filtered:
                filtered = sorted(
                    set(round(x, 4) for x in filtered), key=lambda x: abs(x - pref)
                )
                labels = ["TP1", "TP2", "TP3"]
                for i, tp in enumerate(filtered[:3]):
                    rr = abs(tp - pref) / risk
                    targets.append(
                        TakeProfitLevel(
                            price=round(tp, 4), rr=round(rr, 4), label=labels[i]
                        )
                    )
                if targets:
                    primary_rr = targets[0].rr
                    if primary_rr < config.min_rr:
                        errors.append(
                            f"Primary RR {primary_rr:.2f} below minimum {config.min_rr}"
                        )

    return LevelsResult(entry, sl, targets, primary_rr, errors, warnings)


def validate_trade_levels(
    *,
    bullish: bool,
    entry: Optional[EntryZone],
    stop_loss: Optional[float],
    targets: Sequence[TakeProfitLevel],
    config: StrategyConfig,
    spot: Optional[float] = None,
) -> List[str]:
    errs: List[str] = []
    if entry is None:
        errs.append("Entry missing")
    if stop_loss is None:
        errs.append("SL missing")
    if not targets:
        errs.append("TP missing")
    if entry is None or stop_loss is None:
        return errs
    pref = entry.preferred
    if bullish:
        if stop_loss >= pref:
            errs.append("SL on wrong side for BUY")
        for t in targets:
            if t.price <= pref:
                errs.append(f"{t.label} on wrong side for BUY")
            if spot is not None and t.price <= spot:
                errs.append(f"{t.label} already at/below spot — stale")
    else:
        if stop_loss <= pref:
            errs.append("SL on wrong side for SELL")
        for t in targets:
            if t.price >= pref:
                errs.append(f"{t.label} on wrong side for SELL")
            if spot is not None and t.price >= spot:
                errs.append(f"{t.label} already at/above spot — stale")
    if targets and targets[0].rr < config.min_rr:
        errs.append("RR below minimum")
    if entry.low > entry.high:
        errs.append("Invalid entry zone")
    return errs


def _zone_distance(lo: float, hi: float, price: float) -> float:
    if lo > hi:
        lo, hi = hi, lo
    if lo <= price <= hi:
        return 0.0
    if price < lo:
        return lo - price
    return price - hi


def _entry_zone(
    *,
    bullish: bool,
    price: float,
    smc: Optional[SmcAnalysisResult],
    smc_15m: Optional[SmcAnalysisResult],
    atr: float,
    max_distance: float,
) -> Optional[EntryZone]:
    """
    Prefer reclaim into OB/FVG zone near spot.

    Distant / left-behind zones are ignored so we do not advertise stale
    pullback plans whose TPs price has already run through.
    """
    zone = _best_entry_zone(
        smc, bullish=bullish, price=price, max_distance=max_distance
    ) or _best_entry_zone(
        smc_15m, bullish=bullish, price=price, max_distance=max_distance
    )
    if zone is None:
        return None
    lo = float(zone.low if zone.low is not None else price - atr * 0.2)
    hi = float(zone.high if zone.high is not None else price + atr * 0.2)
    if lo > hi:
        lo, hi = hi, lo
    preferred = price if lo <= price <= hi else (lo + hi) / 2.0
    return EntryZone(low=round(lo, 4), high=round(hi, 4), preferred=round(preferred, 4))


def _best_entry_zone(
    smc: Optional[SmcAnalysisResult],
    *,
    bullish: bool,
    price: float,
    max_distance: float,
) -> Optional[ZoneEvent]:
    if smc is None:
        return None
    want = SmcDirection.BULLISH if bullish else SmcDirection.BEARISH
    candidates: List[ZoneEvent] = []
    if bullish:
        candidates.extend([z for z in smc.demand_zones if z.valid and not z.mitigated])
    else:
        candidates.extend([z for z in smc.supply_zones if z.valid and not z.mitigated])
    candidates.extend(
        [
            z
            for z in smc.order_blocks
            if z.valid and not z.mitigated and z.direction == want
        ]
    )
    for f in smc.fvg:
        if (
            f.valid
            and not f.filled
            and f.direction == want
            and f.lifecycle
            in (FvgLifecycle.CREATED, FvgLifecycle.ACTIVE, FvgLifecycle.PARTIALLY_FILLED)
            and f.low is not None
            and f.high is not None
        ):
            candidates.append(
                ZoneEvent(
                    id=f.id,
                    type=f.type,
                    direction=f.direction,
                    timeframe=f.timeframe,
                    created_index=f.created_index,
                    confirm_index=f.confirm_index,
                    high=f.high,
                    low=f.low,
                    origin_index=f.created_index,
                )
            )

    near: List[tuple[float, int, ZoneEvent]] = []
    for z in candidates:
        if z.low is None or z.high is None:
            continue
        dist = _zone_distance(float(z.low), float(z.high), price)
        if dist <= max_distance:
            near.append((dist, -int(z.confirm_index or 0), z))
    if not near:
        return None
    near.sort(key=lambda item: (item[0], item[1]))
    return near[0][2]


def _stop_loss(
    *,
    bullish: bool,
    price: float,
    entry: Optional[EntryZone],
    smc: Optional[SmcAnalysisResult],
    smc_15m: Optional[SmcAnalysisResult],
    buffer: float,
    max_distance: float,
) -> Optional[float]:
    """Structural SL anchored to the entry zone (not only last close).

    Bug fixed (Path B): previously candidates were filtered with ``c < price``.
    When price had run *above* an FVG/OB entry zone, a swing between entry and
    price could be chosen as SL — leaving SL on the wrong side of
    ``entry.preferred`` and failing validation ("BUY SL must be below entry").
    """
    if entry is not None:
        anchor = float(entry.low) if bullish else float(entry.high)
        preferred = float(entry.preferred)
    else:
        anchor = price
        preferred = price

    candidates: List[float] = []
    for src in (smc_15m, smc):
        if src is None:
            continue
        want = SmcDirection.BULLISH if bullish else SmcDirection.BEARISH
        for s in reversed(src.liquidity_sweeps):
            if s.valid and s.direction == want and s.confirm_index <= src.as_of_index:
                if bullish:
                    candidates.append(float(s.liquidity_level) - buffer)
                else:
                    candidates.append(float(s.liquidity_level) + buffer)
                break
        zone = _best_entry_zone(
            src, bullish=bullish, price=price, max_distance=max_distance
        )
        if zone is not None:
            if bullish and zone.low is not None:
                candidates.append(float(zone.low) - buffer)
            if (not bullish) and zone.high is not None:
                candidates.append(float(zone.high) + buffer)
        if bullish and src.structure.last_swing_low and src.structure.last_swing_low.price:
            candidates.append(float(src.structure.last_swing_low.price) - buffer)
        if (not bullish) and src.structure.last_swing_high and src.structure.last_swing_high.price:
            candidates.append(float(src.structure.last_swing_high.price) + buffer)

    if bullish:
        ceiling = min(anchor, preferred, price)
        valid = [c for c in candidates if c < ceiling]
        if valid:
            return round(max(valid), 4)
        return round(ceiling - max(buffer * 3, abs(ceiling) * 0.0005), 4)

    floor = max(anchor, preferred, price)
    valid = [c for c in candidates if c > floor]
    if valid:
        return round(min(valid), 4)
    return round(floor + max(buffer * 3, abs(floor) * 0.0005), 4)


def _candidate_targets(
    *,
    bullish: bool,
    entry: float,
    smc: Optional[SmcAnalysisResult],
    smc_15m: Optional[SmcAnalysisResult],
) -> List[float]:
    tps: List[float] = []
    for src in (smc_15m, smc):
        if src is None:
            continue
        for pool in src.liquidity:
            if not pool.valid:
                continue
            px = pool.price if pool.price is not None else pool.high if bullish else pool.low
            if px is None:
                continue
            if bullish and pool.type.value == "buy_side_liquidity" and px > entry:
                tps.append(float(px))
            if (not bullish) and pool.type.value == "sell_side_liquidity" and px < entry:
                tps.append(float(px))
        if bullish and src.structure.last_swing_high and src.structure.last_swing_high.price:
            px = float(src.structure.last_swing_high.price)
            if px > entry:
                tps.append(px)
        if (not bullish) and src.structure.last_swing_low and src.structure.last_swing_low.price:
            px = float(src.structure.last_swing_low.price)
            if px < entry:
                tps.append(px)
        dr = src.dealing_range
        if bullish and dr.range_high and dr.range_high > entry:
            tps.append(float(dr.range_high))
        if (not bullish) and dr.range_low and dr.range_low < entry:
            tps.append(float(dr.range_low))
        if bullish:
            for z in src.supply_zones:
                if z.valid and not z.mitigated and z.low and z.low > entry:
                    tps.append(float(z.low))
                    break
        else:
            for z in src.demand_zones:
                if z.valid and not z.mitigated and z.high and z.high < entry:
                    tps.append(float(z.high))
                    break
    return tps
