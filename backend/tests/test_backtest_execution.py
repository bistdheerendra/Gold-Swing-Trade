"""Backtest execution, validation, metrics unit tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.backtest.config import (
    AmbiguityPolicy,
    BacktestConfig,
    BacktestCostConfig,
    BacktestExecutionConfig,
    CostMode,
)
from app.backtest.equity import build_equity_curve
from app.backtest.execution import (
    entry_zone_touched,
    resolve_exit,
    resolve_fill_price,
    validate_levels,
)
from app.backtest.metrics import compute_metrics
from app.backtest.schemas import BacktestTrade, ExitReason, TradeLifecycle
from app.backtest.trades import r_multiple
from app.backtest.validation import chronological_slice, validate_ohlcv_series
from app.market.schemas import OHLCVBar, Timeframe


def _bar(ts: datetime, o: float, h: float, l: float, c: float) -> OHLCVBar:
    return OHLCVBar(
        timestamp=ts,
        symbol="XAUUSD",
        timeframe=Timeframe.M15,
        open=o,
        high=h,
        low=l,
        close=c,
        volume=1.0,
        source="test",
    )


def test_validate_duplicate_timestamps() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = [_bar(t0, 1, 2, 0.5, 1.5), _bar(t0, 1, 2, 0.5, 1.5)]
    report = validate_ohlcv_series(bars, symbol="XAUUSD", min_bars=1)
    assert not report.ok
    assert any("Duplicate" in e for e in report.errors)


def test_validate_invalid_ohlc() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(Exception):
        _bar(t0, 10, 9, 8, 9)  # high < open


def test_buy_entry_zone() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bar = _bar(t0, 100, 105, 99, 104)
    assert entry_zone_touched(bullish=True, bar=bar, low=101, high=103)
    assert not entry_zone_touched(bullish=True, bar=bar, low=106, high=108)


def test_sell_entry_zone() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bar = _bar(t0, 100, 105, 99, 100)
    assert entry_zone_touched(bullish=False, bar=bar, low=102, high=104)


def test_fill_does_not_assume_preferred_outside_range() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bar = _bar(t0, 100, 102, 100, 101)
    cost = BacktestCostConfig(mode=CostMode.ZERO_COST)
    fill = resolve_fill_price(
        bullish=True, bar=bar, zone_low=100, zone_high=105, preferred=104, cost=cost
    )
    assert 100 <= fill <= 102


def test_validate_levels_buy_sell() -> None:
    assert validate_levels(bullish=True, entry=100, sl=99, tp=102) == []
    assert validate_levels(bullish=True, entry=100, sl=101, tp=102)
    assert validate_levels(bullish=False, entry=100, sl=101, tp=98) == []
    assert validate_levels(bullish=False, entry=100, sl=99, tp=98)


def test_ambiguity_conservative_sl_first() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bar = _bar(t0, 100, 110, 90, 105)  # touches SL 95 and TP 108
    cost = BacktestCostConfig(mode=CostMode.ZERO_COST)
    reason, price = resolve_exit(
        bullish=True,
        bar=bar,
        sl=95,
        tp=108,
        policy=AmbiguityPolicy.CONSERVATIVE,
        cost=cost,
    )
    assert reason == "SL"
    assert price == 95


def test_ambiguity_skip() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bar = _bar(t0, 100, 110, 90, 105)
    cost = BacktestCostConfig(mode=CostMode.ZERO_COST)
    reason, price = resolve_exit(
        bullish=True,
        bar=bar,
        sl=95,
        tp=108,
        policy=AmbiguityPolicy.SKIP,
        cost=cost,
    )
    assert reason == "AMBIGUOUS_SKIP"
    assert price is None


def test_r_multiple() -> None:
    assert r_multiple(bullish=True, entry=4350, exit_price=4380, stop_loss=4335) == pytest.approx(2.0)
    assert r_multiple(bullish=True, entry=4350, exit_price=4335, stop_loss=4335) == pytest.approx(-1.0)
    assert r_multiple(bullish=False, entry=4350, exit_price=4320, stop_loss=4365) == pytest.approx(2.0)


def test_metrics_and_equity() -> None:
    trades = [
        BacktestTrade(
            trade_id="1",
            signal_id="s1",
            setup_id="p1",
            symbol="XAUUSD",
            direction="BUY",
            status=TradeLifecycle.TP_HIT,
            signal_time="2024-01-01T00:00:00+00:00",
            signal_index=0,
            entry_price=100,
            stop_loss=99,
            exit_reason=ExitReason.TP1,
            net_r=2.0,
            trading_cost=0,
            trading_cost_r=0,
            duration_bars=3,
        ),
        BacktestTrade(
            trade_id="2",
            signal_id="s2",
            setup_id="p2",
            symbol="XAUUSD",
            direction="SELL",
            status=TradeLifecycle.SL_HIT,
            signal_time="2024-01-01T01:00:00+00:00",
            signal_index=1,
            entry_price=100,
            stop_loss=101,
            exit_reason=ExitReason.SL,
            net_r=-1.0,
            trading_cost=0,
            trading_cost_r=0,
            duration_bars=2,
        ),
    ]
    curve, dd, dd_pct, _, _ = build_equity_curve(
        initial_equity=100_000,
        risk_fraction=0.01,
        closed_trades_net_r=[
            ("2024-01-01T00:30:00+00:00", 1, 2.0),
            ("2024-01-01T02:00:00+00:00", 2, -1.0),
        ],
    )
    assert curve[-1].equity == pytest.approx(101_000)  # +2R then -1R = +1R = +1000
    m = compute_metrics(
        trades,
        total_signals=2,
        signals_expired=0,
        initial_equity=100_000,
        equity_final=curve[-1].equity,
        max_drawdown=dd,
        max_drawdown_pct=dd_pct,
        max_drawdown_start=None,
        max_drawdown_end=None,
    )
    assert m.winning_trades == 1
    assert m.losing_trades == 1
    assert m.win_rate == pytest.approx(0.5)
    assert m.profit_factor == pytest.approx(2.0)
    assert m.expectancy_r == pytest.approx(0.5)


def test_chronological_split_no_shuffle() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bars = [
        _bar(t0 + timedelta(minutes=15 * i), 100 + i, 101 + i, 99 + i, 100 + i)
        for i in range(100)
    ]
    train, _ = chronological_slice(bars, segment="TRAIN")
    test, _ = chronological_slice(bars, segment="TEST")
    assert train[0].timestamp < train[-1].timestamp
    assert train[-1].timestamp < test[0].timestamp


def test_realistic_cost_widens_entry() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    bar = _bar(t0, 100, 105, 99, 102)
    zero = resolve_fill_price(
        bullish=True,
        bar=bar,
        zone_low=100,
        zone_high=103,
        preferred=101,
        cost=BacktestCostConfig(mode=CostMode.ZERO_COST),
    )
    real = resolve_fill_price(
        bullish=True,
        bar=bar,
        zone_low=100,
        zone_high=103,
        preferred=101,
        cost=BacktestCostConfig(
            mode=CostMode.REALISTIC_COST, spread_points=0.4, slippage_points=0.1
        ),
    )
    assert real > zero
