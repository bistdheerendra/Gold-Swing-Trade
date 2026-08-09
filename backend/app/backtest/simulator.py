"""Position / pending-signal simulator."""

from __future__ import annotations

import uuid
from typing import List, Optional

from app.backtest.config import AmbiguityPolicy, BacktestConfig, RiskSizingMode, TpMode
from app.backtest.execution import (
    apply_exit_costs,
    entry_zone_touched,
    resolve_exit,
    resolve_fill_price,
    select_target_price,
    validate_levels,
)
from app.backtest.schemas import (
    BacktestSignalRecord,
    BacktestTrade,
    ExitReason,
    TradeLifecycle,
)
from app.backtest.trades import cash_pnl_from_r, cost_as_r, r_multiple, risk_points
from app.market.schemas import OHLCVBar
from app.strategy.schemas import StrategyAnalyzeResult


class TradeSimulator:
    def __init__(self, config: BacktestConfig) -> None:
        self.config = config
        self.pending: Optional[BacktestTrade] = None
        self.active: Optional[BacktestTrade] = None
        self.trades: List[BacktestTrade] = []
        self.signals: List[BacktestSignalRecord] = []
        self.signals_generated = 0
        self.signals_expired = 0
        # Running equity for RISK_PERCENT cash mapping (same simulator path)
        self.equity = config.initial_equity

    def on_signal(
        self,
        result: StrategyAnalyzeResult,
        *,
        bar_index: int,
        bar: OHLCVBar,
    ) -> None:
        if result.signal.value not in ("BUY", "SELL"):
            return
        if result.entry is None or result.stop_loss is None or not result.targets:
            return
        if self.config.execution.allow_pyramiding is False:
            if self.pending is not None or self.active is not None:
                return

        self.signals_generated += 1
        sid = result.signal_id or str(uuid.uuid4())
        setup = result.setup_id or f"setup_{bar_index}"
        rec = BacktestSignalRecord(
            signal_id=sid,
            setup_id=setup,
            timestamp=bar.timestamp.isoformat(),
            bar_index=bar_index,
            direction=result.signal.value,
            score=result.score,
            status="SIGNAL",
            entry_low=result.entry.low,
            entry_high=result.entry.high,
            preferred_entry=result.entry.preferred,
            stop_loss=result.stop_loss,
            market_state=result.market_context.state,
        )
        self.signals.append(rec)

        tp = select_target_price(
            [t.model_dump() for t in result.targets],
            self.config.execution.tp_mode,
        )
        if tp is None:
            return

        trade = BacktestTrade(
            trade_id=str(uuid.uuid4()),
            signal_id=sid,
            setup_id=setup,
            symbol=result.symbol,
            direction=result.signal.value,
            status=TradeLifecycle.PENDING,
            signal_time=bar.timestamp.isoformat(),
            signal_index=bar_index,
            stop_loss=float(result.stop_loss),
            targets=[t.model_dump() for t in result.targets],
            selected_tp=float(tp),
            score=result.score,
            strategy_version=result.strategy_version,
            market_state=result.market_context.state,
            entry_zone_low=result.entry.low,
            entry_zone_high=result.entry.high,
            preferred_entry=result.entry.preferred,
        )
        self.pending = trade

    def on_bar(self, bar_index: int, bar: OHLCVBar, *, max_age: int) -> None:
        if self.pending is not None:
            self._try_enter_or_expire(bar_index, bar, max_age=max_age)
        if self.active is not None:
            self._manage_active(bar_index, bar)

    def close_open_at_end(self, bar_index: int, bar: OHLCVBar) -> None:
        if self.pending is not None:
            self.pending.status = TradeLifecycle.EXPIRED
            self.signals_expired += 1
            self.trades.append(self.pending)
            self.pending = None
        if self.active is not None:
            bullish = self.active.direction == "BUY"
            px = apply_exit_costs(
                bullish=bullish, price=bar.close, cost=self.config.cost
            )
            self._close(self.active, bar_index, bar, px, ExitReason.END_OF_DATA)
            self.active = None

    def _try_enter_or_expire(self, bar_index: int, bar: OHLCVBar, *, max_age: int) -> None:
        assert self.pending is not None
        age = bar_index - self.pending.signal_index
        if age > max_age:
            self.pending.status = TradeLifecycle.EXPIRED
            self.signals_expired += 1
            self.trades.append(self.pending)
            self.pending = None
            return

        bullish = self.pending.direction == "BUY"
        touched = entry_zone_touched(
            bullish=bullish,
            bar=bar,
            low=self.pending.entry_zone_low,
            high=self.pending.entry_zone_high,
        )
        if not touched:
            return

        fill = resolve_fill_price(
            bullish=bullish,
            bar=bar,
            zone_low=self.pending.entry_zone_low,
            zone_high=self.pending.entry_zone_high,
            preferred=self.pending.preferred_entry,
            cost=self.config.cost,
        )
        tp = self.pending.selected_tp
        if tp is None:
            self.pending.status = TradeLifecycle.CANCELLED
            self.trades.append(self.pending)
            self.pending = None
            return
        errs = validate_levels(
            bullish=bullish, entry=fill, sl=self.pending.stop_loss, tp=tp
        )
        if errs:
            self.pending.status = TradeLifecycle.CANCELLED
            self.pending.metadata["cancel_reason"] = "; ".join(errs)
            self.trades.append(self.pending)
            self.pending = None
            return

        self.pending.entry_price = fill
        self.pending.entry_time = bar.timestamp.isoformat()
        self.pending.entry_index = bar_index
        self.pending.risk_points = risk_points(
            bullish=bullish, entry=fill, stop_loss=self.pending.stop_loss
        )
        self.pending.status = TradeLifecycle.ACTIVE
        self.active = self.pending
        self.pending = None

        # Same-candle SL/TP after entry
        self._manage_active(bar_index, bar)

    def _manage_active(self, bar_index: int, bar: OHLCVBar) -> None:
        assert self.active is not None
        trade = self.active
        if trade.entry_price is None or trade.selected_tp is None:
            return
        bullish = trade.direction == "BUY"
        reason, price = resolve_exit(
            bullish=bullish,
            bar=bar,
            sl=trade.stop_loss,
            tp=trade.selected_tp,
            policy=self.config.execution.ambiguity_policy,
            cost=self.config.cost,
        )
        if reason is None:
            return
        if reason == "AMBIGUOUS_SKIP":
            trade.status = TradeLifecycle.AMBIGUOUS_SKIP
            trade.exit_reason = ExitReason.AMBIGUOUS_SKIP
            trade.exit_time = bar.timestamp.isoformat()
            trade.exit_index = bar_index
            trade.duration_bars = bar_index - (trade.entry_index or trade.signal_index)
            self.trades.append(trade)
            self.active = None
            return
        exit_reason = ExitReason.SL if reason == "SL" else ExitReason.TP1
        if reason == "TP":
            mode = self.config.execution.tp_mode
            if mode == TpMode.TP2:
                exit_reason = ExitReason.TP2
            elif mode == TpMode.TP3:
                exit_reason = ExitReason.TP3
            else:
                exit_reason = ExitReason.TP1
        assert price is not None
        self._close(trade, bar_index, bar, price, exit_reason)
        self.active = None

    def _close(
        self,
        trade: BacktestTrade,
        bar_index: int,
        bar: OHLCVBar,
        exit_price: float,
        reason: ExitReason,
    ) -> None:
        bullish = trade.direction == "BUY"
        assert trade.entry_price is not None
        gross = r_multiple(
            bullish=bullish,
            entry=trade.entry_price,
            exit_price=exit_price,
            stop_loss=trade.stop_loss,
        )
        commission = self.config.cost.effective_commission()
        eq_for_risk = (
            self.equity
            if self.config.risk_mode == RiskSizingMode.RISK_PERCENT
            else None
        )
        # Round-trip commission once at close
        c_r = cost_as_r(
            commission=commission,
            risk_points_value=trade.risk_points or 1.0,
            risk_fraction=self.config.risk_fraction_per_trade,
            initial_equity=self.config.initial_equity,
            equity_for_risk=eq_for_risk,
        )
        # Spread/slippage already in prices; commission in R
        net = gross - c_r
        trade.exit_price = exit_price
        trade.exit_time = bar.timestamp.isoformat()
        trade.exit_index = bar_index
        trade.exit_reason = reason
        trade.gross_r = round(gross, 6)
        trade.trading_cost_r = round(c_r, 6)
        trade.net_r = round(net, 6)
        trade.trading_cost = commission
        trade.gross_pnl = cash_pnl_from_r(
            gross,
            initial_equity=self.config.initial_equity,
            risk_fraction=self.config.risk_fraction_per_trade,
            equity_for_risk=eq_for_risk,
        )
        trade.net_pnl = cash_pnl_from_r(
            net,
            initial_equity=self.config.initial_equity,
            risk_fraction=self.config.risk_fraction_per_trade,
            equity_for_risk=eq_for_risk,
        )
        if self.config.risk_mode == RiskSizingMode.RISK_PERCENT:
            self.equity = self.equity + float(trade.net_pnl)
        trade.duration_bars = bar_index - (trade.entry_index or trade.signal_index)
        trade.status = (
            TradeLifecycle.SL_HIT if reason == ExitReason.SL else TradeLifecycle.TP_HIT
        )
        if reason == ExitReason.END_OF_DATA:
            trade.status = TradeLifecycle.CANCELLED
        if reason == ExitReason.CANCELLED:
            trade.status = TradeLifecycle.CANCELLED
        self.trades.append(trade)
