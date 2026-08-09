"""Setup detection — scores BUY and SELL sides independently."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.mtf.schemas import MultiTimeframeResult
from app.smc.schemas import SmcAnalysisResult
from app.strategy.conditions import (
    DirectionalContext,
    detect_strong_conflict,
    score_buy_conditions,
    score_sell_conditions,
    total_score,
)
from app.strategy.config import StrategyConfig
from app.strategy.schemas import ConditionScore


@dataclass
class ScoredSetup:
    bullish: bool
    score: int
    conditions: List[ConditionScore]
    conflict_reason: Optional[str]


def detect_setups(
    *,
    mtf: MultiTimeframeResult,
    smc_4h: Optional[SmcAnalysisResult],
    smc_1h: Optional[SmcAnalysisResult],
    smc_15m: Optional[SmcAnalysisResult],
    as_of_index_15m: int,
    config: StrategyConfig,
) -> tuple[ScoredSetup, ScoredSetup]:
    ctx = DirectionalContext(
        smc_4h=smc_4h,
        smc_1h=smc_1h,
        smc_15m=smc_15m,
        mtf=mtf,
        as_of_index_15m=as_of_index_15m,
    )
    buy_conds = score_buy_conditions(ctx, config)
    sell_conds = score_sell_conditions(ctx, config)
    buy = ScoredSetup(
        bullish=True,
        score=total_score(buy_conds, config.score_weights),
        conditions=buy_conds,
        conflict_reason=detect_strong_conflict(ctx, bullish=True),
    )
    sell = ScoredSetup(
        bullish=False,
        score=total_score(sell_conds, config.score_weights),
        conditions=sell_conds,
        conflict_reason=detect_strong_conflict(ctx, bullish=False),
    )

    # Optional hard requirements → zero-out / flag via conflict
    if config.liquidity_required:
        if not any(c.key == "liquidity_sweep" and c.met for c in buy.conditions):
            buy.conflict_reason = buy.conflict_reason or "Liquidity required but missing (BUY)"
        if not any(c.key == "liquidity_sweep" and c.met for c in sell.conditions):
            sell.conflict_reason = sell.conflict_reason or "Liquidity required but missing (SELL)"

    if config.require_structure_confirmation:
        if not any(c.key == "bos_choch" and c.met for c in buy.conditions):
            # Soft: reduce score rather than hard block — already 0 points
            pass
        if not any(c.key == "bos_choch" and c.met for c in sell.conditions):
            pass

    if config.minimum_htf_alignment:
        # If 4H structure condition fully failed for a side, treat as conflict when score would fire
        for setup in (buy, sell):
            struct = next((c for c in setup.conditions if c.key == "structure_4h"), None)
            htf = next((c for c in setup.conditions if c.key == "higher_tf_bias"), None)
            if struct and htf and (not struct.met) and (not htf.met) and setup.score >= config.signal_threshold:
                setup.conflict_reason = (
                    setup.conflict_reason or "HTF/4H alignment failed"
                )

    return buy, sell
