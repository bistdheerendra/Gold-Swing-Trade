"""SMC analysis engine — single timeframe, causal."""

from __future__ import annotations

from typing import Optional, Sequence

from app.market.schemas import OHLCVBar
from app.smc.dealing_range import compute_dealing_range
from app.smc.fvg import detect_fvgs
from app.smc.liquidity import detect_liquidity_pools, detect_liquidity_sweeps
from app.smc.order_blocks import detect_order_blocks, zones_from_order_blocks
from app.smc.schemas import (
    SmcAnalysisResult,
    SmcConfig,
    SmcDirection,
    SmcEvent,
    SmcEventType,
    SmcStructureSummary,
)
from app.smc.score import build_summary, compute_smc_score
from app.smc.structure_breaks import detect_bos_choch
from app.ta.structure import SwingType, detect_swings


class SmcEngine:
    def __init__(self, config: Optional[SmcConfig] = None) -> None:
        self.config = config or SmcConfig()

    def analyze(
        self,
        bars: Sequence[OHLCVBar],
        *,
        symbol: str,
        timeframe: str,
        as_of_index: Optional[int] = None,
    ) -> SmcAnalysisResult:
        if not bars:
            raise ValueError("bars must be non-empty")
        end = len(bars) - 1 if as_of_index is None else as_of_index
        if end < 0 or end >= len(bars):
            raise ValueError("as_of_index out of range")

        window = list(bars[: end + 1])
        opens = [b.open for b in window]
        highs = [b.high for b in window]
        lows = [b.low for b in window]
        closes = [b.close for b in window]
        cfg = self.config

        swings = detect_swings(
            highs,
            lows,
            left=cfg.swing_left,
            right=cfg.swing_right,
            as_of_index=end,
        )
        bos, choch, bias = detect_bos_choch(
            highs,
            lows,
            closes,
            swings,
            timeframe=timeframe,
            config=cfg,
            as_of_index=end,
        )
        fvgs = detect_fvgs(
            highs, lows, timeframe=timeframe, config=cfg, as_of_index=end
        )
        order_blocks = detect_order_blocks(
            opens,
            highs,
            lows,
            closes,
            bos,
            timeframe=timeframe,
            config=cfg,
            as_of_index=end,
        )
        demand, supply = zones_from_order_blocks(order_blocks)
        pools = detect_liquidity_pools(
            swings, timeframe=timeframe, config=cfg, as_of_index=end
        )
        sweeps = detect_liquidity_sweeps(
            highs,
            lows,
            closes,
            pools,
            timeframe=timeframe,
            config=cfg,
            as_of_index=end,
        )
        dealing = compute_dealing_range(
            swings, closes, config=cfg, as_of_index=end
        )

        swing_high_events = [
            SmcEvent(
                id=f"swing_high:{timeframe}:{s.confirm_index}:{s.pivot_index}",
                type=SmcEventType.SWING_HIGH,
                direction=SmcDirection.BEARISH,
                timeframe=timeframe,
                created_index=s.pivot_index,
                confirm_index=s.confirm_index,
                price=s.price,
                high=s.price,
                valid=True,
                metadata={"label": None if s.label is None else s.label.value},
            )
            for s in swings
            if s.type == SwingType.HIGH
        ]
        swing_low_events = [
            SmcEvent(
                id=f"swing_low:{timeframe}:{s.confirm_index}:{s.pivot_index}",
                type=SmcEventType.SWING_LOW,
                direction=SmcDirection.BULLISH,
                timeframe=timeframe,
                created_index=s.pivot_index,
                confirm_index=s.confirm_index,
                price=s.price,
                low=s.price,
                valid=True,
                metadata={"label": None if s.label is None else s.label.value},
            )
            for s in swings
            if s.type == SwingType.LOW
        ]

        structure = SmcStructureSummary(
            bias=bias,
            swing_highs=swing_high_events,
            swing_lows=swing_low_events,
            last_swing_high=swing_high_events[-1] if swing_high_events else None,
            last_swing_low=swing_low_events[-1] if swing_low_events else None,
        )

        result = SmcAnalysisResult(
            symbol=symbol,
            timeframe=timeframe,
            bar_count=len(window),
            as_of_index=end,
            as_of_timestamp=window[-1].timestamp.isoformat(),
            config=cfg,
            structure=structure,
            bos=bos,
            choch=choch,
            fvg=fvgs,
            order_blocks=order_blocks,
            demand_zones=demand,
            supply_zones=supply,
            liquidity=pools,
            liquidity_sweeps=sweeps,
            dealing_range=dealing,
        )
        result.smc_score = compute_smc_score(result)
        result.summary = build_summary(result)
        return result
