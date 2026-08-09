"""Event-driven historical backtest engine."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Mapping, Optional, Sequence

from app.backtest.config import BacktestConfig
from app.backtest.equity import build_equity_curve
from app.backtest.metrics import compute_metrics
from app.backtest.report import build_breakdowns
from app.backtest.schemas import BacktestResult
from app.backtest.simulator import TradeSimulator
from app.backtest.validation import (
    chronological_eval_bounds,
    chronological_slice,
    validate_ohlcv_series,
)
from app.market.schemas import (
    ANALYSIS_TIMEFRAMES,
    OHLCVBar,
    Timeframe,
    ensure_utc,
    parse_timeframe,
)
from app.mtf.sync import candle_close_time
from app.strategy.config import StrategyConfig
from app.strategy.engine import SignalStore, StrategyEngine


HTF_CHAIN = ANALYSIS_TIMEFRAMES


def resample_ohlcv(bars: Sequence[OHLCVBar], target_tf: str) -> List[OHLCVBar]:
    """Naive OHLCV resample for HTF when only finer bars are available."""
    if not bars:
        return []
    tf = parse_timeframe(target_tf)
    src_tf = bars[0].timeframe if isinstance(bars[0].timeframe, Timeframe) else parse_timeframe(str(bars[0].timeframe))
    if src_tf == tf:
        return list(bars)
    buckets: Dict[datetime, List[OHLCVBar]] = {}
    for b in bars:
        ts = ensure_utc(b.timestamp)
        # Floor to period
        if tf == Timeframe.H1:
            key = ts.replace(minute=0, second=0, microsecond=0)
        elif tf == Timeframe.H4:
            key = ts.replace(hour=(ts.hour // 4) * 4, minute=0, second=0, microsecond=0)
        elif tf == Timeframe.D1:
            key = ts.replace(hour=0, minute=0, second=0, microsecond=0)
        elif tf == Timeframe.M15:
            key = ts.replace(minute=(ts.minute // 15) * 15, second=0, microsecond=0)
        else:
            key = ts
        buckets.setdefault(key, []).append(b)
    out: List[OHLCVBar] = []
    for key in sorted(buckets.keys()):
        chunk = buckets[key]
        out.append(
            OHLCVBar(
                timestamp=key,
                symbol=chunk[0].symbol,
                timeframe=tf,
                open=chunk[0].open,
                high=max(x.high for x in chunk),
                low=min(x.low for x in chunk),
                close=chunk[-1].close,
                volume=sum(x.volume for x in chunk),
                source=f"resample:{chunk[0].source}",
            )
        )
    return out


class BacktestEngine:
    """
    Walks entry-timeframe candles forward in time.
    At each closed candle, runs Phase 6 StrategyEngine with as_of = candle close.
    Does not modify strategy logic.
    """

    def __init__(
        self,
        config: Optional[BacktestConfig] = None,
        *,
        strategy_config: Optional[StrategyConfig] = None,
    ) -> None:
        self.config = config or BacktestConfig()
        self.strategy_config = strategy_config or StrategyConfig(
            strategy_version=self.config.strategy_version
        )

    def run(
        self,
        bars_by_tf: Mapping[str, Sequence[OHLCVBar]],
        *,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        split_segment: str = "ALL",
    ) -> BacktestResult:
        entry_tf = self.config.entry_timeframe
        raw_entry = list(bars_by_tf.get(entry_tf, []))
        if not raw_entry and "15m" in bars_by_tf:
            raw_entry = list(bars_by_tf["15m"])
            entry_tf = "15m"

        # Ensure HTF series exist (resample from entry if needed)
        prepared: Dict[str, List[OHLCVBar]] = {}
        base = raw_entry
        for tf in HTF_CHAIN:
            if tf in bars_by_tf and bars_by_tf[tf]:
                prepared[tf] = list(bars_by_tf[tf])
            elif base:
                prepared[tf] = resample_ohlcv(base, tf)
            else:
                prepared[tf] = []

        entry_bars = prepared.get(entry_tf, [])
        # Date filter on entry
        if start:
            start_u = ensure_utc(start)
            entry_bars = [b for b in entry_bars if ensure_utc(b.timestamp) >= start_u]
        if end:
            end_u = ensure_utc(end)
            entry_bars = [b for b in entry_bars if ensure_utc(b.timestamp) <= end_u]

        # Keep FULL chronological series for causal context / warmup.
        # Only evaluate signals inside the segment bounds (Phase 11.6).
        # Previous behavior sliced first then applied warmup on the short TEST
        # window — that could zero out all evaluations when TEST < warmup_bars.
        eval_start, eval_end, seg_name = chronological_eval_bounds(
            len(entry_bars),
            segment=split_segment,
            train_ratio=self.config.split.train_ratio,
            validation_ratio=self.config.split.validation_ratio,
            test_ratio=self.config.split.test_ratio,
        )
        # Still expose sliced view for fingerprint/reporting of the eval window
        eval_bars = entry_bars[eval_start:eval_end]
        report = validate_ohlcv_series(
            entry_bars,
            symbol=self.config.symbol,
            min_bars=max(30, self.config.warmup_bars // 2),
        )
        if not report.ok:
            raise ValueError("; ".join(report.errors))
        if not eval_bars:
            raise ValueError(f"Empty evaluation segment: {seg_name}")

        data_version = _data_fingerprint(eval_bars)
        store = SignalStore()
        strategy = StrategyEngine(config=self.strategy_config, store=store)
        combined = None
        mode = (self.config.signal_mode or "RULE_ONLY").upper()
        if mode in ("ML_FILTER", "COMBINED"):
            from app.combined.config import CombinedSignalConfig
            from app.combined.engine import CombinedSignalEngine

            ccfg = CombinedSignalConfig(
                model_id=self.config.model_id,
                min_ml_confidence=self.config.min_ml_confidence
                if self.config.min_ml_confidence is not None
                else 0.60,
            )
            combined = CombinedSignalEngine(
                config=ccfg,
                strategy_config=self.strategy_config,
                store=store,
            )
            combined.ensure_model(self.config.model_id)
            if (
                self.config.min_ml_confidence is None
                and combined._runtime is not None
            ):
                # freeze validation-selected threshold from artifact
                combined.config = combined.config.model_copy(
                    update={"min_ml_confidence": combined._runtime.selected_threshold}
                )

        sim = TradeSimulator(self.config)
        max_age = (
            self.config.execution.max_signal_age_bars
            if self.config.execution.max_signal_age_bars is not None
            else self.strategy_config.max_signal_age_bars
        )

        notes = [
            f"split={seg_name}",
            f"eval_bars={len(eval_bars)}",
            f"context_bars={len(entry_bars)}",
            f"eval_index=[{eval_start},{eval_end})",
            f"signal_mode={mode}",
            (
                f"risk_mode={self.config.risk_mode.value}: "
                + (
                    "FIXED_1R uses initial_equity * risk_fraction (research normalization)."
                    if self.config.risk_mode.value == "FIXED_1R"
                    else "RISK_PERCENT compounds 1R from current equity (account simulation)."
                )
            ),
            f"ambiguity_policy={self.config.execution.ambiguity_policy.value}",
            f"cost_mode={self.config.cost.mode.value}",
            "Warmup uses full-series context; signals only counted inside eval segment",
            f"max_context_bars={self.config.max_context_bars}",
        ]
        if combined is not None:
            notes.append(f"model_id={combined.config.model_id}")
            notes.append(f"min_ml_confidence={combined.config.min_ml_confidence}")
            notes.append("ML model not retrained during backtest")
        notes.extend(report.warnings)

        # Event loop — full series for causality; evaluate only inside segment
        step = max(1, self.config.step)
        for i, bar in enumerate(entry_bars):
            in_eval = eval_start <= i < eval_end
            if i < self.config.warmup_bars:
                continue
            if not in_eval:
                # Outside eval window: still advance open trades if any were carried
                # (normally none before first eval signal).
                sim.on_bar(i, bar, max_age=max_age)
                continue
            if (i - max(eval_start, self.config.warmup_bars)) % step != 0 and i != eval_end - 1:
                # Still manage open trades every bar inside eval window
                sim.on_bar(i, bar, max_age=max_age)
                continue

            as_of = candle_close_time(bar, entry_tf)
            # Truncate series for explicit causality (defense in depth beyond strategy as_of)
            # Cap lookback: scanning 16k+ bars per TF per step is CPU-prohibitive and
            # unnecessary for local SMC/TA windows (Phase 11.6 expanded history).
            max_ctx = max(100, int(self.config.max_context_bars))
            windowed = {}
            for tf, series in prepared.items():
                clipped = [
                    b
                    for b in series
                    if ensure_utc(b.timestamp) <= ensure_utc(bar.timestamp)
                ]
                windowed[tf] = clipped[-max_ctx:]
            # Always manage pending/active first on this bar, then new signals
            # (entry on signal bar allowed after signal — strategy sees closed bar)
            try:
                if combined is not None:
                    cresult = combined.analyze(
                        windowed,
                        symbol=self.config.symbol,
                        as_of=as_of,
                        timeframes=list(HTF_CHAIN),
                        model_id=self.config.model_id,
                        mode=mode,
                    )
                    result = cresult.as_strategy_result()
                else:
                    result = strategy.analyze(
                        windowed,
                        symbol=self.config.symbol,
                        as_of=as_of,
                        timeframes=list(HTF_CHAIN),
                    )
            except Exception as exc:  # noqa: BLE001 — keep backtest running
                notes.append(f"strategy skip @ {i}: {exc}")
                sim.on_bar(i, bar, max_age=max_age)
                continue

            sim.on_signal(result, bar_index=i, bar=bar)
            sim.on_bar(i, bar, max_age=max_age)

        if entry_bars:
            sim.close_open_at_end(len(entry_bars) - 1, entry_bars[-1])

        closed_for_equity = [
            (t.exit_time or t.signal_time, t.exit_index or t.signal_index, t.net_r or 0.0)
            for t in sim.trades
            if t.net_r is not None and t.exit_reason is not None
        ]
        equity_curve, max_dd, max_dd_pct, dd_start, dd_end = build_equity_curve(
            initial_equity=self.config.initial_equity,
            risk_fraction=self.config.risk_fraction_per_trade,
            closed_trades_net_r=closed_for_equity,
            risk_mode=self.config.risk_mode,
        )
        final_eq = equity_curve[-1].equity if equity_curve else self.config.initial_equity
        metrics = compute_metrics(
            sim.trades,
            total_signals=sim.signals_generated,
            signals_expired=sim.signals_expired,
            initial_equity=self.config.initial_equity,
            equity_final=final_eq,
            max_drawdown=max_dd,
            max_drawdown_pct=max_dd_pct,
            max_drawdown_start=dd_start,
            max_drawdown_end=dd_end,
        )
        breakdowns = build_breakdowns(sim.trades)
        backtest_id = str(uuid.uuid4())
        start_iso = eval_bars[0].timestamp.isoformat() if eval_bars else ""
        end_iso = eval_bars[-1].timestamp.isoformat() if eval_bars else ""

        return BacktestResult(
            backtest_id=backtest_id,
            symbol=self.config.symbol.upper(),
            entry_timeframe=entry_tf,
            start=start_iso,
            end=end_iso,
            strategy_version=self.config.strategy_version,
            data_version=data_version,
            config=self.config,
            summary={
                "total_signals": metrics.total_signals,
                "trades_entered": metrics.trades_entered,
                "signals_expired": metrics.signals_expired,
                "win_rate": metrics.win_rate,
                "profit_factor": metrics.profit_factor,
                "expectancy_r": metrics.expectancy_r,
                "net_profit_r": metrics.net_profit_r,
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "average_r": metrics.average_r,
                "final_equity": metrics.final_equity,
                "split": seg_name,
            },
            metrics=metrics,
            equity_curve=equity_curve,
            trades=sim.trades,
            signals=sim.signals,
            breakdowns=breakdowns,
            warnings=report.warnings,
            notes=notes,
        )


def _data_fingerprint(bars: Sequence[OHLCVBar]) -> str:
    h = hashlib.sha1()
    h.update(f"{len(bars)}".encode())
    if bars:
        h.update(bars[0].timestamp.isoformat().encode())
        h.update(bars[-1].timestamp.isoformat().encode())
        h.update(f"{bars[0].close}:{bars[-1].close}".encode())
    return h.hexdigest()[:16]


# In-memory result store for API
_BACKTEST_STORE: Dict[str, BacktestResult] = {}


def store_result(result: BacktestResult) -> BacktestResult:
    _BACKTEST_STORE[result.backtest_id] = result
    return result


def get_result(backtest_id: str) -> Optional[BacktestResult]:
    return _BACKTEST_STORE.get(backtest_id)


def clear_results() -> None:
    _BACKTEST_STORE.clear()
