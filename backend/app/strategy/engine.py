"""StrategyEngine — orchestrates MTF/TA/SMC → BUY/SELL/WAIT/NO_TRADE."""

from __future__ import annotations

import hashlib
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Mapping, Optional, Sequence

from app.market.schemas import OHLCVBar, ensure_utc, parse_timeframe
from app.mtf.analyzer import DEFAULT_TFS, MultiTimeframeAnalyzer
from app.mtf.schemas import BiasWeights, MultiTimeframeResult
from app.mtf.sync import closed_window
from app.smc.engine import SmcEngine
from app.smc.schemas import SmcAnalysisResult, SmcConfig
from app.strategy.confidence import direction_from_scores, score_band
from app.strategy.config import StrategyConfig
from app.strategy.explanation import build_reasons, build_risks
from app.strategy.filters import MarketConditionFilter, classify_volatility
from app.strategy.schemas import (
    MarketCondition,
    MarketContext,
    SetupLifecycle,
    SignalDirection,
    SignalStatus,
    StrategyAnalyzeResult,
    StrategySignal,
    VolatilityBand,
)
from app.strategy.setup_detector import detect_setups
from app.strategy.signal_engine import compute_levels, validate_trade_levels
from app.ta.engine import TechnicalAnalysisEngine
from app.ta.schemas import TechnicalAnalysisConfig


class SignalStore:
    """In-memory signal history + setup deduplication (Phase 6)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_setup: Dict[str, StrategySignal] = {}
        self._history: List[StrategySignal] = []

    def get_active(self, setup_id: str) -> Optional[StrategySignal]:
        with self._lock:
            sig = self._by_setup.get(setup_id)
            if sig and sig.status in (
                SignalStatus.DETECTED,
                SignalStatus.CONFIRMED,
                SignalStatus.ACTIVE,
            ):
                return sig
            return None

    def upsert(self, signal: StrategySignal, *, is_new: bool) -> StrategySignal:
        with self._lock:
            existing = self._by_setup.get(signal.setup_id)
            if existing and not is_new:
                # Refresh fields but keep signal_id / first timestamp
                updated = signal.model_copy(
                    update={
                        "signal_id": existing.signal_id,
                        "timestamp": existing.timestamp,
                    }
                )
                self._by_setup[signal.setup_id] = updated
                # Replace last matching history entry if present
                for i in range(len(self._history) - 1, -1, -1):
                    if self._history[i].signal_id == existing.signal_id:
                        self._history[i] = updated
                        break
                return updated
            self._by_setup[signal.setup_id] = signal
            self._history.append(signal)
            return signal

    def mark_status(self, setup_id: str, status: SignalStatus) -> None:
        with self._lock:
            sig = self._by_setup.get(setup_id)
            if not sig:
                return
            updated = sig.model_copy(
                update={"status": status, "setup_lifecycle": SetupLifecycle(status.value)}
            )
            self._by_setup[setup_id] = updated
            for i in range(len(self._history) - 1, -1, -1):
                if self._history[i].signal_id == sig.signal_id:
                    self._history[i] = updated
                    break

    def history(
        self, *, symbol: Optional[str] = None, limit: int = 100
    ) -> List[StrategySignal]:
        with self._lock:
            items = list(self._history)
        if symbol:
            items = [s for s in items if s.symbol == symbol.upper()]
        return list(reversed(items[-limit:]))

    def clear(self) -> None:
        with self._lock:
            self._by_setup.clear()
            self._history.clear()


# Process-wide store for API history
_GLOBAL_STORE = SignalStore()


def get_signal_store() -> SignalStore:
    return _GLOBAL_STORE


def reset_signal_store() -> None:
    _GLOBAL_STORE.clear()


class StrategyEngine:
    """
    Deterministic rule-based signal engine.

    Consumes Phase 3/4/5 engines without modifying them.
    """

    def __init__(
        self,
        config: Optional[StrategyConfig] = None,
        *,
        store: Optional[SignalStore] = None,
        market_filter: Optional[MarketConditionFilter] = None,
        bias_weights: Optional[BiasWeights] = None,
        ta_config: Optional[TechnicalAnalysisConfig] = None,
        smc_config: Optional[SmcConfig] = None,
    ) -> None:
        self.config = config or StrategyConfig()
        self.store = store or get_signal_store()
        self.market_filter = market_filter or MarketConditionFilter()
        self.mtf_analyzer = MultiTimeframeAnalyzer(
            weights=bias_weights, ta_config=ta_config, smc_config=smc_config
        )
        self.ta_engine = TechnicalAnalysisEngine(ta_config)
        self.smc_engine = SmcEngine(smc_config)

    def analyze(
        self,
        bars_by_tf: Mapping[str, Sequence[OHLCVBar]],
        *,
        symbol: str,
        as_of: datetime,
        timeframes: Sequence[str] = DEFAULT_TFS,
    ) -> StrategyAnalyzeResult:
        as_of_utc = ensure_utc(as_of)
        notes: List[str] = []

        mtf = self.mtf_analyzer.analyze(
            bars_by_tf,
            symbol=symbol,
            as_of=as_of_utc,
            timeframes=timeframes,
        )

        smc_4h, idx_4h, win_4h = self._smc_window(bars_by_tf, "4h", symbol, as_of_utc)
        smc_1h, idx_1h, win_1h = self._smc_window(bars_by_tf, "1h", symbol, as_of_utc)
        smc_15m, idx_15m, win_15m = self._smc_window(bars_by_tf, "15m", symbol, as_of_utc)

        if idx_15m is None or len(win_15m) < 50:
            notes.append("Insufficient 15M closed bars for strategy")
            return self._empty_result(
                symbol, as_of_utc, mtf, notes, SignalDirection.NO_TRADE, 0, "Insufficient data"
            )

        ta_15m = self.ta_engine.analyze(
            win_15m, symbol=symbol, timeframe="15m", as_of_index=idx_15m
        )
        volatility = classify_volatility(ta_15m, self.config)
        market_condition = self.market_filter.evaluate()

        buy_setup, sell_setup = detect_setups(
            mtf=mtf,
            smc_4h=smc_4h,
            smc_1h=smc_1h,
            smc_15m=smc_15m,
            as_of_index_15m=idx_15m,
            config=self.config,
        )

        # Volatility / market hard blocks
        vol_hard = (
            self.config.atr_filter_enabled and volatility == VolatilityBand.EXTREME
        )
        market_hard = (
            self.config.reject_unsafe_market
            and market_condition == MarketCondition.UNSAFE
        )

        # Apply high-vol penalty to scores
        buy_score = buy_setup.score
        sell_score = sell_setup.score
        if (
            self.config.atr_filter_enabled
            and volatility == VolatilityBand.HIGH
        ):
            buy_score = max(0, int(buy_score - self.config.high_volatility_penalty))
            sell_score = max(0, int(sell_score - self.config.high_volatility_penalty))
            notes.append("High volatility score penalty applied")

        buy_levels = compute_levels(
            bullish=True,
            bars_15m=win_15m,
            smc_1h=smc_1h,
            smc_15m=smc_15m,
            atr=ta_15m.latest.atr,
            config=self.config,
        )
        sell_levels = compute_levels(
            bullish=False,
            bars_15m=win_15m,
            smc_1h=smc_1h,
            smc_15m=smc_15m,
            atr=ta_15m.latest.atr,
            config=self.config,
        )

        buy_val_errs = validate_trade_levels(
            bullish=True,
            entry=buy_levels.entry,
            stop_loss=buy_levels.stop_loss,
            targets=buy_levels.targets,
            config=self.config,
        )
        sell_val_errs = validate_trade_levels(
            bullish=False,
            entry=sell_levels.entry,
            stop_loss=sell_levels.stop_loss,
            targets=sell_levels.targets,
            config=self.config,
        )

        # Only hard-block BUY/SELL validation when score would otherwise qualify
        buy_hard = vol_hard or market_hard or (
            buy_score >= self.config.signal_threshold and bool(buy_val_errs or buy_levels.errors)
        )
        sell_hard = vol_hard or market_hard or (
            sell_score >= self.config.signal_threshold and bool(sell_val_errs or sell_levels.errors)
        )
        # Always hard block on extreme/unsafe
        if vol_hard or market_hard:
            buy_hard = True
            sell_hard = True

        direction, chosen_score, decision_note = direction_from_scores(
            buy_score=buy_score,
            sell_score=sell_score,
            config=self.config,
            buy_hard_block=buy_hard,
            sell_hard_block=sell_hard,
            buy_conflict=bool(buy_setup.conflict_reason),
            sell_conflict=bool(sell_setup.conflict_reason),
        )
        notes.append(decision_note)

        # Pick conditions / levels for chosen side (or best for WAIT)
        if direction == SignalDirection.BUY:
            conditions = buy_setup.conditions
            levels = buy_levels
            bullish = True
            side_score = buy_score
        elif direction == SignalDirection.SELL:
            conditions = sell_setup.conditions
            levels = sell_levels
            bullish = False
            side_score = sell_score
        else:
            # Prefer higher score side for explanation
            if buy_score >= sell_score:
                conditions = buy_setup.conditions
                levels = buy_levels
                bullish = True
                side_score = buy_score
            else:
                conditions = sell_setup.conditions
                levels = sell_levels
                bullish = False
                side_score = sell_score

        if buy_setup.conflict_reason and bullish:
            notes.append(f"BUY conflict: {buy_setup.conflict_reason}")
        if sell_setup.conflict_reason and not bullish:
            notes.append(f"SELL conflict: {sell_setup.conflict_reason}")
        if vol_hard:
            notes.append("Extreme volatility → NO_TRADE")
            direction = SignalDirection.NO_TRADE
        if market_hard:
            notes.append("Market condition UNSAFE → NO_TRADE")
            direction = SignalDirection.NO_TRADE

        # If BUY/SELL but validation failed somehow, downgrade
        if direction in (SignalDirection.BUY, SignalDirection.SELL):
            val = validate_trade_levels(
                bullish=bullish,
                entry=levels.entry,
                stop_loss=levels.stop_loss,
                targets=levels.targets,
                config=self.config,
            )
            if val or levels.errors:
                notes.extend(val or levels.errors)
                direction = SignalDirection.NO_TRADE

        extra_risks = list(levels.warnings)
        if buy_setup.conflict_reason and direction != SignalDirection.BUY:
            extra_risks.append(buy_setup.conflict_reason)
        if sell_setup.conflict_reason and direction != SignalDirection.SELL:
            extra_risks.append(sell_setup.conflict_reason)

        reasons = build_reasons(
            direction, conditions, primary_rr=levels.primary_rr if direction in (SignalDirection.BUY, SignalDirection.SELL) else None
        )
        risks = build_risks(
            volatility=volatility,
            conditions=conditions,
            primary_rr=levels.primary_rr,
            min_rr=self.config.min_rr,
            extra=extra_risks,
        )

        context = MarketContext(
            htf_bias=mtf.higher_timeframe_bias.value,
            setup_bias=mtf.setup_bias.value,
            entry_bias=mtf.entry_bias.value,
            state=mtf.state.value,
            alignment_score=mtf.alignment_score,
        )

        setup_id = self._setup_id(
            symbol=symbol,
            direction=direction if direction in (SignalDirection.BUY, SignalDirection.SELL) else (
                SignalDirection.BUY if bullish else SignalDirection.SELL
            ),
            smc_1h=smc_1h,
            smc_15m=smc_15m,
            as_of_index=idx_15m,
        )

        # Lifecycle / dedup / expiration
        status = self._map_status(direction)
        expires_at = idx_15m + self.config.max_signal_age_bars
        existing = self.store.get_active(setup_id)

        # Expire old setups past age
        if existing and existing.expires_at_bar_index is not None:
            if idx_15m > existing.expires_at_bar_index:
                self.store.mark_status(setup_id, SignalStatus.EXPIRED)
                existing = None
                notes.append("Previous setup EXPIRED")

        current: Optional[StrategySignal] = None
        if direction in (SignalDirection.BUY, SignalDirection.SELL):
            is_new = not (existing is not None and existing.direction == direction)
            if not is_new and existing is not None:
                notes.append("Duplicate setup suppressed — refreshing existing signal")
                signal_id = existing.signal_id
                timestamp = existing.timestamp
            else:
                signal_id = str(uuid.uuid4())
                timestamp = as_of_utc.isoformat()
            signal = StrategySignal(
                signal_id=signal_id,
                setup_id=setup_id,
                symbol=symbol.upper(),
                timestamp=timestamp,
                as_of=as_of_utc.isoformat(),
                direction=direction,
                status=status,
                score=side_score,
                score_label=f"{side_score}/100 strategy condition score",
                entry=levels.entry,
                stop_loss=levels.stop_loss,
                targets=levels.targets,
                primary_rr=levels.primary_rr,
                market_context=context,
                conditions=list(conditions),
                reasons=reasons,
                risks=risks,
                volatility=volatility,
                market_condition=market_condition,
                strategy_version=self.config.strategy_version,
                setup_lifecycle=SetupLifecycle(status.value),
                expires_at_bar_index=expires_at,
                entry_timeframe="15m",
                metadata={
                    "score_band": score_band(side_score, self.config),
                    "buy_score": buy_score,
                    "sell_score": sell_score,
                    "as_of_index_15m": idx_15m,
                },
            )
            current = self.store.upsert(signal, is_new=is_new)
        else:
            # Non-trade outcomes are returned but not always stored; store WAIT/NO_TRADE snapshots lightly
            signal = StrategySignal(
                signal_id=str(uuid.uuid4()),
                setup_id=setup_id,
                symbol=symbol.upper(),
                timestamp=as_of_utc.isoformat(),
                as_of=as_of_utc.isoformat(),
                direction=direction,
                status=status,
                score=side_score,
                score_label=f"{side_score}/100 strategy condition score",
                # Keep computed levels for research display even on NO_TRADE/WAIT.
                # UI must treat them as candidates when signal is not BUY/SELL.
                entry=levels.entry,
                stop_loss=levels.stop_loss,
                targets=list(levels.targets),
                primary_rr=levels.primary_rr,
                market_context=context,
                conditions=list(conditions),
                reasons=reasons,
                risks=risks,
                volatility=volatility,
                market_condition=market_condition,
                strategy_version=self.config.strategy_version,
                setup_lifecycle=SetupLifecycle(status.value),
                expires_at_bar_index=expires_at,
                metadata={
                    "score_band": score_band(side_score, self.config),
                    "buy_score": buy_score,
                    "sell_score": sell_score,
                    "as_of_index_15m": idx_15m,
                    "levels_are_candidates": direction
                    not in (SignalDirection.BUY, SignalDirection.SELL),
                },
            )
            current = signal

        return StrategyAnalyzeResult(
            symbol=symbol.upper(),
            as_of=as_of_utc.isoformat(),
            signal=direction,
            score=side_score,
            score_label=f"{side_score}/100 strategy condition score",
            status=status,
            setup_id=setup_id,
            signal_id=current.signal_id if current else None,
            entry=current.entry if current else None,
            stop_loss=current.stop_loss if current else None,
            targets=current.targets if current else [],
            primary_rr=current.primary_rr if current else None,
            market_context=context,
            conditions=list(conditions),
            reasons=reasons,
            risks=risks,
            volatility=volatility,
            market_condition=market_condition,
            strategy_version=self.config.strategy_version,
            config=self.config,
            current=current,
            notes=notes,
        )

    def _smc_window(
        self,
        bars_by_tf: Mapping[str, Sequence[OHLCVBar]],
        tf_key: str,
        symbol: str,
        as_of: datetime,
    ) -> tuple[Optional[SmcAnalysisResult], Optional[int], list]:
        tf = parse_timeframe(tf_key)
        raw = list(bars_by_tf.get(tf.value, bars_by_tf.get(tf_key, [])))
        window, idx = closed_window(raw, tf, as_of)
        if idx is None or len(window) < 30:
            return None, idx, window
        smc = self.smc_engine.analyze(
            window, symbol=symbol, timeframe=tf.value, as_of_index=idx
        )
        return smc, idx, window

    def _setup_id(
        self,
        *,
        symbol: str,
        direction: SignalDirection,
        smc_1h: Optional[SmcAnalysisResult],
        smc_15m: Optional[SmcAnalysisResult],
        as_of_index: int,
    ) -> str:
        """
        Stable id for a setup cluster.

        Uses last directional break/sweep ids when present; buckets by entry-bar window
        so the same structure does not spam new signals every candle.
        """
        parts = [symbol.upper(), direction.value]
        for smc in (smc_1h, smc_15m):
            if smc is None:
                continue
            if smc.bos:
                parts.append(smc.bos[-1].id)
            if smc.choch:
                parts.append(smc.choch[-1].id)
            if smc.liquidity_sweeps:
                parts.append(smc.liquidity_sweeps[-1].id)
        # Bucket index so micro-changes don't create new setups every bar
        bucket = as_of_index // max(1, self.config.max_signal_age_bars // 2 or 1)
        parts.append(str(bucket))
        digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]
        return f"setup_{digest}"

    def _map_status(self, direction: SignalDirection) -> SignalStatus:
        if direction in (SignalDirection.BUY, SignalDirection.SELL):
            return SignalStatus.CONFIRMED
        if direction == SignalDirection.WAIT:
            return SignalStatus.DETECTED
        return SignalStatus.INVALIDATED

    def _empty_result(
        self,
        symbol: str,
        as_of: datetime,
        mtf: MultiTimeframeResult,
        notes: List[str],
        direction: SignalDirection,
        score: int,
        reason: str,
    ) -> StrategyAnalyzeResult:
        context = MarketContext(
            htf_bias=mtf.higher_timeframe_bias.value,
            setup_bias=mtf.setup_bias.value,
            entry_bias=mtf.entry_bias.value,
            state=mtf.state.value,
            alignment_score=mtf.alignment_score,
        )
        return StrategyAnalyzeResult(
            symbol=symbol.upper(),
            as_of=ensure_utc(as_of).isoformat(),
            signal=direction,
            score=score,
            score_label=f"{score}/100 strategy condition score",
            status=SignalStatus.INVALIDATED,
            market_context=context,
            reasons=[reason],
            risks=[],
            strategy_version=self.config.strategy_version,
            config=self.config,
            notes=notes,
        )
