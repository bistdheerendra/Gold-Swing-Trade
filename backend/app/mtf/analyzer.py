"""MultiTimeframeAnalyzer — orchestrates per-TF TA + SMC + bias."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Mapping, Optional, Sequence

from app.market.schemas import MTF_HIERARCHY, OHLCVBar, Timeframe, ensure_utc, parse_timeframe
from app.mtf.bias import BiasEngine, label_from_score
from app.mtf.schemas import (
    BiasLabel,
    BiasWeights,
    MtfLayerSummary,
    MtfState,
    MultiTimeframeResult,
    StructureLabel,
    TimeframeAnalysis,
)
from app.mtf.sync import closed_window
from app.smc.engine import SmcEngine
from app.smc.schemas import FvgLifecycle, SmcConfig, SmcDirection
from app.ta.engine import TechnicalAnalysisEngine
from app.ta.schemas import TechnicalAnalysisConfig

TF_ROLES = {
    "1d": "macro",
    "4h": "structure",
    "1h": "setup",
    "30m": "timing",
    "15m": "entry",
}

DEFAULT_TFS = MTF_HIERARCHY


class MultiTimeframeAnalyzer:
    """
    Independently runs TA + SMC per timeframe, then aggregates context.
    Does not modify TA/SMC detector internals.
    """

    def __init__(
        self,
        *,
        weights: Optional[BiasWeights] = None,
        ta_config: Optional[TechnicalAnalysisConfig] = None,
        smc_config: Optional[SmcConfig] = None,
    ) -> None:
        self.weights = weights or BiasWeights()
        self.bias_engine = BiasEngine(self.weights)
        self.ta_engine = TechnicalAnalysisEngine(ta_config)
        self.smc_engine = SmcEngine(smc_config)

    def analyze(
        self,
        bars_by_tf: Mapping[str, Sequence[OHLCVBar]],
        *,
        symbol: str,
        as_of: datetime,
        timeframes: Sequence[str] = DEFAULT_TFS,
    ) -> MultiTimeframeResult:
        as_of_utc = ensure_utc(as_of)
        per_tf: Dict[str, TimeframeAnalysis] = {}
        notes: list[str] = []

        for tf_key in timeframes:
            tf = parse_timeframe(tf_key)
            raw = list(bars_by_tf.get(tf.value, bars_by_tf.get(tf_key, [])))
            window, idx = closed_window(raw, tf, as_of_utc)
            if idx is None or len(window) < 30:
                notes.append(f"{tf.value}: insufficient closed bars")
                per_tf[tf.value] = TimeframeAnalysis(
                    timeframe=tf.value,
                    role=TF_ROLES.get(tf.value, "unknown"),
                    trend=BiasLabel.NEUTRAL,
                    structure=StructureLabel.NEUTRAL,
                    momentum=BiasLabel.NEUTRAL,
                    volatility="UNKNOWN",
                    smc_bias=BiasLabel.NEUTRAL,
                    bias_score=0,
                )
                continue

            ta = self.ta_engine.analyze(
                window, symbol=symbol, timeframe=tf.value, as_of_index=idx
            )
            smc = self.smc_engine.analyze(
                window, symbol=symbol, timeframe=tf.value, as_of_index=idx
            )
            bias_score, ta_score, trend, structure, momentum, volatility = (
                self.bias_engine.score_timeframe(ta, smc)
            )
            per_tf[tf.value] = TimeframeAnalysis(
                timeframe=tf.value,
                role=TF_ROLES.get(tf.value, "unknown"),
                trend=trend,
                structure=structure,
                momentum=momentum,
                volatility=volatility,
                smc_bias=_smc_bias_label(smc.structure.bias),
                last_bos=_dir(smc.bos[-1].direction) if smc.bos else None,
                last_choch=_dir(smc.choch[-1].direction) if smc.choch else None,
                active_fvg=_active_fvg(smc),
                active_order_block=_active_ob(smc),
                liquidity_state=_liquidity_state(smc),
                dealing_range=smc.dealing_range.zone.value,
                ta_score=ta_score,
                smc_score=smc.smc_score,
                bias_score=bias_score,
            )

        macro = _layer(per_tf, "1d")
        structure_layer = _layer(per_tf, "4h")
        setup = _layer(per_tf, "1h")
        timing = _layer(per_tf, "30m")
        entry = _layer(per_tf, "15m")

        higher = _combine_bias(macro.bias, structure_layer.bias)
        alignment = _alignment_score(per_tf)
        state = _derive_state(higher, setup.bias, entry.bias, per_tf)

        return MultiTimeframeResult(
            symbol=symbol,
            as_of=as_of_utc.isoformat(),
            timeframes=per_tf,
            macro=macro,
            structure=structure_layer,
            setup=setup,
            timing=timing,
            entry=entry,
            higher_timeframe_bias=higher,
            setup_bias=setup.bias,
            entry_bias=entry.bias,
            alignment_score=alignment,
            state=state,
            weights=self.weights,
            notes=notes,
        )


def _layer(per_tf: Dict[str, TimeframeAnalysis], key: str) -> MtfLayerSummary:
    row = per_tf.get(key)
    if row is None:
        return MtfLayerSummary(bias=BiasLabel.NEUTRAL, timeframe=key, bias_score=0)
    return MtfLayerSummary(
        bias=label_from_score(row.bias_score),
        timeframe=key,
        bias_score=row.bias_score,
    )


def _smc_bias_label(direction: SmcDirection) -> BiasLabel:
    if direction == SmcDirection.BULLISH:
        return BiasLabel.BULLISH
    if direction == SmcDirection.BEARISH:
        return BiasLabel.BEARISH
    return BiasLabel.NEUTRAL


def _dir(direction: SmcDirection) -> str:
    return direction.value


def _active_fvg(smc) -> Optional[str]:
    for f in reversed(smc.fvg):
        if f.valid and f.lifecycle in (
            FvgLifecycle.ACTIVE,
            FvgLifecycle.PARTIALLY_FILLED,
        ):
            return f"{f.direction.value} FVG"
    return None


def _active_ob(smc) -> Optional[str]:
    for z in reversed(smc.order_blocks):
        if z.valid:
            return f"{z.direction.value} OB"
    return None


def _liquidity_state(smc) -> Optional[str]:
    if not smc.liquidity_sweeps:
        if smc.liquidity:
            return f"{len(smc.liquidity)} pools"
        return None
    last = smc.liquidity_sweeps[-1]
    return (
        "Sell-side swept"
        if last.direction == SmcDirection.BULLISH
        else "Buy-side swept"
    )


def _combine_bias(a: BiasLabel, b: BiasLabel) -> BiasLabel:
    if a == b:
        return a
    if a == BiasLabel.NEUTRAL:
        return b
    if b == BiasLabel.NEUTRAL:
        return a
    return BiasLabel.NEUTRAL  # disagree → neutral HTF blend


def _alignment_score(per_tf: Dict[str, TimeframeAnalysis]) -> int:
    scores = [per_tf[k].bias_score for k in MTF_HIERARCHY if k in per_tf]
    if not scores:
        return 0
    # Agreement: low variance around mean sign → high alignment
    mean = sum(scores) / len(scores)
    if abs(mean) < 1:
        # all near zero
        spread = sum(abs(s - mean) for s in scores) / len(scores)
        return max(0, min(100, int(100 - spread)))
    # fraction of TFs sharing the dominant sign
    dominant = 1 if mean > 0 else -1
    agree = sum(1 for s in scores if (s >= 30 and dominant > 0) or (s <= -30 and dominant < 0) or abs(s) < 30)
    # Better: count same-side non-neutral
    same = sum(1 for s in scores if (dominant > 0 and s > 0) or (dominant < 0 and s < 0))
    base = int(100 * same / len(scores))
    # penalize entry disagreement
    if "15m" in per_tf and "1h" in per_tf:
        if (per_tf["15m"].bias_score > 0) != (per_tf["1h"].bias_score > 0) and abs(
            per_tf["15m"].bias_score
        ) >= 30:
            base = max(0, base - 15)
    return max(0, min(100, base))


def _derive_state(
    higher: BiasLabel,
    setup: BiasLabel,
    entry: BiasLabel,
    per_tf: Dict[str, TimeframeAnalysis],
) -> MtfState:
    labels = [higher, setup, entry]
    if all(x == BiasLabel.NEUTRAL for x in labels):
        return MtfState.NEUTRAL

    # ranging if most TF structures ranging
    ranging = sum(
        1
        for k in MTF_HIERARCHY
        if k in per_tf and per_tf[k].structure.value == "RANGING"
    )
    if ranging >= 2 and higher == BiasLabel.NEUTRAL:
        return MtfState.RANGING

    if higher != BiasLabel.NEUTRAL and setup == higher and entry == higher:
        return MtfState.TRENDING

    if higher != BiasLabel.NEUTRAL and setup == higher and entry != higher:
        if entry == BiasLabel.NEUTRAL or (
            (higher == BiasLabel.BULLISH and entry == BiasLabel.BEARISH)
            or (higher == BiasLabel.BEARISH and entry == BiasLabel.BULLISH)
        ):
            return MtfState.PULLBACK

    if higher != BiasLabel.NEUTRAL and setup != higher and setup != BiasLabel.NEUTRAL:
        return MtfState.REVERSAL_RISK

    if (
        higher != BiasLabel.NEUTRAL
        and entry != BiasLabel.NEUTRAL
        and higher != entry
        and setup != higher
    ):
        return MtfState.CONFLICT

    if higher != entry and entry != BiasLabel.NEUTRAL and higher != BiasLabel.NEUTRAL:
        return MtfState.CONFLICT

    return MtfState.NEUTRAL
