"""Deterministic BiasEngine — market context only, not prediction."""

from __future__ import annotations

from typing import Optional

from app.mtf.schemas import BiasLabel, BiasWeights, StructureLabel
from app.smc.schemas import DealingZone, FvgLifecycle, SmcAnalysisResult, SmcDirection
from app.ta.schemas import TechnicalAnalysisResult
from app.ta.structure import StructureLabel as SwingLabel


def label_from_score(score: int) -> BiasLabel:
    if score >= 30:
        return BiasLabel.BULLISH
    if score <= -30:
        return BiasLabel.BEARISH
    return BiasLabel.NEUTRAL


def strength_band(score: int) -> str:
    if score >= 70:
        return "STRONG_BULLISH"
    if score >= 30:
        return "BULLISH"
    if score <= -70:
        return "STRONG_BEARISH"
    if score <= -30:
        return "BEARISH"
    return "NEUTRAL"


class BiasEngine:
    def __init__(self, weights: Optional[BiasWeights] = None) -> None:
        self.weights = weights or BiasWeights()

    def score_timeframe(
        self,
        ta: TechnicalAnalysisResult,
        smc: SmcAnalysisResult,
    ) -> tuple[int, int, BiasLabel, StructureLabel, BiasLabel, str]:
        """
        Returns:
          bias_score (-100..100),
          ta_score (-100..100),
          trend,
          structure,
          momentum,
          volatility_label
        """
        w = self.weights
        total_w = max(w.total(), 1e-9)

        ema_s = self._ema_component(ta)  # -1..1
        struct_s = self._structure_component(ta, smc)
        bos_s = self._bos_component(smc)
        choch_s = self._choch_component(smc)
        mom_s = self._momentum_component(ta)
        liq_s = self._liquidity_component(smc)

        raw = (
            ema_s * w.ema_weight
            + struct_s * w.structure_weight
            + bos_s * w.bos_weight
            + choch_s * w.choch_weight
            + mom_s * w.momentum_weight
            + liq_s * w.liquidity_weight
        ) / total_w

        bias_score = int(max(-100, min(100, round(raw * 100))))
        ta_only = (ema_s * w.ema_weight + mom_s * w.momentum_weight) / max(
            w.ema_weight + w.momentum_weight, 1e-9
        )
        ta_score = int(max(-100, min(100, round(ta_only * 100))))

        trend = label_from_score(int(round(ema_s * 100)))
        structure = self._structure_label(ta, smc, struct_s)
        momentum = label_from_score(int(round(mom_s * 100)))
        volatility = self._volatility_label(ta)
        return bias_score, ta_score, trend, structure, momentum, volatility

    def _ema_component(self, ta: TechnicalAnalysisResult) -> float:
        latest = ta.latest
        closes_proxy = latest.ema_20
        if latest.ema_20 is None or latest.ema_50 is None:
            return 0.0
        bull = 0
        bear = 0
        if latest.ema_20 > latest.ema_50:
            bull += 1
        else:
            bear += 1
        if latest.ema_50 is not None and latest.ema_100 is not None:
            if latest.ema_50 > latest.ema_100:
                bull += 1
            else:
                bear += 1
        if latest.ema_100 is not None and latest.ema_200 is not None:
            if latest.ema_100 > latest.ema_200:
                bull += 1
            else:
                bear += 1
        # slope proxy: ema20 vs ema50 distance sign already counted; mild weight on price vs ema20 via close≈ last ema if missing
        _ = closes_proxy
        if bull + bear == 0:
            return 0.0
        return (bull - bear) / (bull + bear)

    def _structure_component(
        self, ta: TechnicalAnalysisResult, smc: SmcAnalysisResult
    ) -> float:
        labels = ta.structure.recent_labels
        if not labels:
            # fall back to SMC bias
            if smc.structure.bias == SmcDirection.BULLISH:
                return 0.5
            if smc.structure.bias == SmcDirection.BEARISH:
                return -0.5
            return 0.0
        score = 0.0
        for lab in labels[-4:]:
            if lab in (SwingLabel.HIGHER_HIGH, SwingLabel.HIGHER_LOW):
                score += 1
            elif lab in (SwingLabel.LOWER_HIGH, SwingLabel.LOWER_LOW):
                score -= 1
        return max(-1.0, min(1.0, score / 4.0))

    def _structure_label(
        self,
        ta: TechnicalAnalysisResult,
        smc: SmcAnalysisResult,
        struct_s: float,
    ) -> StructureLabel:
        if abs(struct_s) < 0.15 and smc.structure.bias == SmcDirection.NEUTRAL:
            return StructureLabel.RANGING if ta.structure.swings else StructureLabel.NEUTRAL
        if struct_s >= 0.25 or smc.structure.bias == SmcDirection.BULLISH:
            return StructureLabel.BULLISH
        if struct_s <= -0.25 or smc.structure.bias == SmcDirection.BEARISH:
            return StructureLabel.BEARISH
        return StructureLabel.NEUTRAL

    def _bos_component(self, smc: SmcAnalysisResult) -> float:
        if not smc.bos:
            return 0.0
        last = smc.bos[-1]
        return 1.0 if last.direction == SmcDirection.BULLISH else -1.0

    def _choch_component(self, smc: SmcAnalysisResult) -> float:
        if not smc.choch:
            return 0.0
        last = smc.choch[-1]
        # Recent CHoCH is a bias flip signal — use its direction
        return 1.0 if last.direction == SmcDirection.BULLISH else -1.0

    def _momentum_component(self, ta: TechnicalAnalysisResult) -> float:
        score = 0.0
        n = 0
        if ta.latest.rsi is not None:
            n += 1
            if ta.latest.rsi >= 55:
                score += 1
            elif ta.latest.rsi <= 45:
                score -= 1
        if ta.latest.macd is not None and ta.latest.macd_signal is not None:
            n += 1
            if ta.latest.macd > ta.latest.macd_signal:
                score += 1
            else:
                score -= 1
        if ta.latest.adx is not None and ta.latest.plus_di is not None and ta.latest.minus_di is not None:
            n += 1
            if ta.latest.adx >= 20:
                if ta.latest.plus_di > ta.latest.minus_di:
                    score += 1
                else:
                    score -= 1
        return 0.0 if n == 0 else score / n

    def _liquidity_component(self, smc: SmcAnalysisResult) -> float:
        score = 0.0
        if smc.liquidity_sweeps:
            last = smc.liquidity_sweeps[-1]
            score += 1.0 if last.direction == SmcDirection.BULLISH else -1.0
        active_ob = next((z for z in reversed(smc.order_blocks) if z.valid), None)
        if active_ob is not None:
            score += 0.5 if active_ob.direction == SmcDirection.BULLISH else -0.5
        active_fvg = next(
            (
                f
                for f in reversed(smc.fvg)
                if f.valid
                and f.lifecycle in (FvgLifecycle.ACTIVE, FvgLifecycle.PARTIALLY_FILLED)
            ),
            None,
        )
        if active_fvg is not None:
            score += 0.5 if active_fvg.direction == SmcDirection.BULLISH else -0.5
        zone = smc.dealing_range.zone
        if zone == DealingZone.DISCOUNT:
            score += 0.25
        elif zone == DealingZone.PREMIUM:
            score -= 0.25
        return max(-1.0, min(1.0, score / 2.0))

    def _volatility_label(self, ta: TechnicalAnalysisResult) -> str:
        atr = ta.latest.atr
        close_proxy = ta.latest.ema_20
        if atr is None or close_proxy is None or close_proxy == 0:
            return "UNKNOWN"
        ratio = atr / abs(close_proxy)
        if ratio < 0.0015:
            return "LOW"
        if ratio > 0.004:
            return "HIGH"
        return "NORMAL"
