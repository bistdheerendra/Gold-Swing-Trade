"""Liquidity pools and sweeps."""

from __future__ import annotations

from typing import List, Sequence

from app.ta.structure import SwingPoint, SwingType
from app.smc.schemas import (
    LiquidityPool,
    SmcConfig,
    SmcDirection,
    SmcEventType,
    SweepEvent,
)


def detect_liquidity_pools(
    swings: Sequence[SwingPoint],
    *,
    timeframe: str,
    config: SmcConfig,
    as_of_index: int,
) -> List[LiquidityPool]:
    known = [s for s in swings if s.confirm_index <= as_of_index]
    known = known[-config.liq_lookback_swings :]
    highs = [s for s in known if s.type == SwingType.HIGH]
    lows = [s for s in known if s.type == SwingType.LOW]
    pools: List[LiquidityPool] = []
    pools.extend(
        _cluster(
            highs,
            side=SmcDirection.BEARISH,  # buy-side liquidity sits above highs (bearish sweep target)
            etype=SmcEventType.BUY_SIDE_LIQUIDITY,
            timeframe=timeframe,
            config=config,
            use_max=True,
        )
    )
    pools.extend(
        _cluster(
            lows,
            side=SmcDirection.BULLISH,
            etype=SmcEventType.SELL_SIDE_LIQUIDITY,
            timeframe=timeframe,
            config=config,
            use_max=False,
        )
    )
    return pools


def detect_liquidity_sweeps(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    pools: Sequence[LiquidityPool],
    *,
    timeframe: str,
    config: SmcConfig,
    as_of_index: int,
) -> List[SweepEvent]:
    sweeps: List[SweepEvent] = []
    for pool in pools:
        if pool.confirm_index > as_of_index or pool.price is None:
            continue
        level = pool.price
        if pool.type == SmcEventType.BUY_SIDE_LIQUIDITY:
            sweep = _bearish_sweep(
                highs, lows, closes, level, pool, timeframe, config, as_of_index
            )
        else:
            sweep = _bullish_sweep(
                highs, lows, closes, level, pool, timeframe, config, as_of_index
            )
        if sweep is not None:
            sweeps.append(sweep)
    return sweeps


def _cluster(
    swings: Sequence[SwingPoint],
    *,
    side: SmcDirection,
    etype: SmcEventType,
    timeframe: str,
    config: SmcConfig,
    use_max: bool,
) -> List[LiquidityPool]:
    if not swings:
        return []
    ordered = sorted(swings, key=lambda s: s.price)
    clusters: List[List[SwingPoint]] = []
    current = [ordered[0]]
    for swing in ordered[1:]:
        if abs(swing.price - current[-1].price) <= config.liq_cluster_tolerance:
            current.append(swing)
        else:
            clusters.append(current)
            current = [swing]
    clusters.append(current)

    pools: List[LiquidityPool] = []
    for cluster in clusters:
        if len(cluster) < config.liq_min_touches:
            continue
        level = max(s.price for s in cluster) if use_max else min(s.price for s in cluster)
        confirm = max(s.confirm_index for s in cluster)
        created = min(s.pivot_index for s in cluster)
        pools.append(
            LiquidityPool(
                id=f"{etype.value}:{timeframe}:{confirm}:{level:.5f}",
                type=etype,
                direction=side,
                timeframe=timeframe,
                created_index=created,
                confirm_index=confirm,
                price=float(level),
                high=float(level) if use_max else None,
                low=None if use_max else float(level),
                touches=len(cluster),
                member_pivots=[s.pivot_index for s in cluster],
                valid=True,
            )
        )
    return pools


def _bearish_sweep(
    highs, lows, closes, level, pool, timeframe, config, as_of_index
) -> SweepEvent | None:
    for t_p in range(pool.confirm_index, as_of_index + 1):
        if highs[t_p] <= level + config.sweep_min_penetration:
            continue
        penetration = float(highs[t_p] - level)
        if not config.sweep_require_close_reclaim:
            return _sweep(
                SmcDirection.BEARISH, timeframe, level, t_p, t_p, penetration, pool
            )
        end = min(as_of_index, t_p + config.sweep_max_bars_for_reclaim)
        for t_c in range(t_p, end + 1):
            if closes[t_c] < level:
                return _sweep(
                    SmcDirection.BEARISH, timeframe, level, t_p, t_c, penetration, pool
                )
        # pierce without reclaim in window — failed; keep searching later pierces
    return None


def _bullish_sweep(
    highs, lows, closes, level, pool, timeframe, config, as_of_index
) -> SweepEvent | None:
    for t_p in range(pool.confirm_index, as_of_index + 1):
        if lows[t_p] >= level - config.sweep_min_penetration:
            continue
        penetration = float(level - lows[t_p])
        if not config.sweep_require_close_reclaim:
            return _sweep(
                SmcDirection.BULLISH, timeframe, level, t_p, t_p, penetration, pool
            )
        end = min(as_of_index, t_p + config.sweep_max_bars_for_reclaim)
        for t_c in range(t_p, end + 1):
            if closes[t_c] > level:
                return _sweep(
                    SmcDirection.BULLISH, timeframe, level, t_p, t_c, penetration, pool
                )
    return None


def _sweep(direction, timeframe, level, sweep_index, confirm, penetration, pool) -> SweepEvent:
    return SweepEvent(
        id=f"liquidity_sweep:{timeframe}:{confirm}:{pool.id}",
        type=SmcEventType.LIQUIDITY_SWEEP,
        direction=direction,
        timeframe=timeframe,
        created_index=sweep_index,
        confirm_index=confirm,
        liquidity_level=float(level),
        sweep_index=sweep_index,
        penetration=penetration,
        price=float(level),
        valid=True,
        metadata={"pool_id": pool.id},
    )
