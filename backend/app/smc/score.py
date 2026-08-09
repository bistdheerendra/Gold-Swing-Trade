"""SMC scoring for dashboard snapshot (not a trade signal)."""

from __future__ import annotations

from app.smc.schemas import (
    DealingZone,
    FvgLifecycle,
    SmcAnalysisResult,
    SmcDirection,
)


def compute_smc_score(result: SmcAnalysisResult) -> int:
    bias = result.structure.bias
    score = 0
    if bias in (SmcDirection.BULLISH, SmcDirection.BEARISH):
        score += 20

    if result.bos:
        last = result.bos[-1]
        if last.direction == bias:
            score += 20

    active_fvg = [
        f
        for f in result.fvg
        if f.valid and f.lifecycle in (FvgLifecycle.ACTIVE, FvgLifecycle.PARTIALLY_FILLED)
        and f.direction == bias
    ]
    if active_fvg:
        score += 15

    active_ob = [z for z in result.order_blocks if z.valid and z.direction == bias]
    if active_ob:
        score += 15

    aligned_sweep = [s for s in result.liquidity_sweeps if s.direction == bias]
    if aligned_sweep:
        score += 15

    zone = result.dealing_range.zone
    if bias == SmcDirection.BULLISH and zone == DealingZone.DISCOUNT:
        score += 15
    elif bias == SmcDirection.BEARISH and zone == DealingZone.PREMIUM:
        score += 15

    return min(100, score)


def build_summary(result: SmcAnalysisResult) -> dict:
    last_bos = result.bos[-1] if result.bos else None
    last_choch = result.choch[-1] if result.choch else None
    active_fvg = next(
        (
            f
            for f in reversed(result.fvg)
            if f.valid
            and f.lifecycle in (FvgLifecycle.ACTIVE, FvgLifecycle.PARTIALLY_FILLED)
        ),
        None,
    )
    active_ob = next((z for z in reversed(result.order_blocks) if z.valid), None)
    last_sweep = result.liquidity_sweeps[-1] if result.liquidity_sweeps else None
    return {
        "structure": result.structure.bias.value,
        "last_bos": None if last_bos is None else last_bos.direction.value,
        "last_choch": None if last_choch is None else last_choch.direction.value,
        "liquidity": None
        if last_sweep is None
        else (
            "Sell-side swept"
            if last_sweep.direction == SmcDirection.BULLISH
            else "Buy-side swept"
        ),
        "fvg": None
        if active_fvg is None
        else f"{active_fvg.direction.value.title()} FVG active",
        "order_block": None
        if active_ob is None
        else f"{active_ob.direction.value.title()} OB active",
        "dealing_range": result.dealing_range.zone.value,
        "smc_score": result.smc_score,
    }
