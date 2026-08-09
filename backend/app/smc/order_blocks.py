"""Order blocks and demand/supply zones."""

from __future__ import annotations

from typing import List, Sequence

from app.smc.schemas import (
    BosEvent,
    SmcConfig,
    SmcDirection,
    SmcEventType,
    ZoneEvent,
)


def detect_order_blocks(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    bos_events: Sequence[BosEvent],
    *,
    timeframe: str,
    config: SmcConfig,
    as_of_index: int,
) -> List[ZoneEvent]:
    if config.ob_require_bos and not bos_events:
        return []

    zones: List[ZoneEvent] = []
    for bos in bos_events:
        if bos.confirm_index > as_of_index:
            continue
        ob = _ob_for_bos(
            opens, highs, lows, closes, bos, timeframe=timeframe, config=config
        )
        if ob is None:
            continue
        _apply_mitigation(ob, highs, lows, as_of_index)
        zones.append(ob)
    return zones


def zones_from_order_blocks(order_blocks: Sequence[ZoneEvent]) -> tuple[List[ZoneEvent], List[ZoneEvent]]:
    demand: List[ZoneEvent] = []
    supply: List[ZoneEvent] = []
    for ob in order_blocks:
        if ob.direction == SmcDirection.BULLISH:
            demand.append(
                ob.model_copy(
                    update={
                        "id": ob.id.replace("order_block", "demand_zone"),
                        "type": SmcEventType.DEMAND_ZONE,
                    }
                )
            )
        else:
            supply.append(
                ob.model_copy(
                    update={
                        "id": ob.id.replace("order_block", "supply_zone"),
                        "type": SmcEventType.SUPPLY_ZONE,
                    }
                )
            )
    return demand, supply


def _ob_for_bos(
    opens: Sequence[float],
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    bos: BosEvent,
    *,
    timeframe: str,
    config: SmcConfig,
) -> ZoneEvent | None:
    t_bos = bos.confirm_index
    start = max(0, t_bos - config.ob_lookback)
    candidate_idx: int | None = None
    candidate_ratio = 0.0

    for i in range(start, t_bos):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        rng = max(h - l, 1e-12)
        body = abs(c - o)
        ratio = body / rng
        if ratio < config.ob_min_body_ratio:
            continue
        if bos.direction == SmcDirection.BULLISH and c < o:
            candidate_idx = i
            candidate_ratio = ratio
        elif bos.direction == SmcDirection.BEARISH and c > o:
            candidate_idx = i
            candidate_ratio = ratio

    if candidate_idx is None:
        return None

    i = candidate_idx
    return ZoneEvent(
        id=f"{SmcEventType.ORDER_BLOCK.value}:{timeframe}:{bos.confirm_index}:{i}",
        type=SmcEventType.ORDER_BLOCK,
        direction=bos.direction,
        timeframe=timeframe,
        created_index=i,
        confirm_index=bos.confirm_index,
        high=float(highs[i]),
        low=float(lows[i]),
        origin_index=i,
        strength=min(1.0, candidate_ratio),
        mitigated=False,
        valid=True,
        metadata={"bos_id": bos.id},
    )


def _apply_mitigation(
    zone: ZoneEvent,
    highs: Sequence[float],
    lows: Sequence[float],
    as_of_index: int,
) -> None:
    assert zone.high is not None and zone.low is not None
    for t in range(zone.confirm_index + 1, as_of_index + 1):
        if zone.direction == SmcDirection.BULLISH and lows[t] <= zone.low:
            zone.mitigated = True
            zone.mitigation_index = t
            zone.valid = False
            return
        if zone.direction == SmcDirection.BEARISH and highs[t] >= zone.high:
            zone.mitigated = True
            zone.mitigation_index = t
            zone.valid = False
            return
