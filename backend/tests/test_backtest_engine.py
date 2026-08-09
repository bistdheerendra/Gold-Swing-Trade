"""Backtest engine leakage, reproducibility, expiration (with stubbed strategy)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence

import pytest

from app.backtest.config import (
    AmbiguityPolicy,
    BacktestConfig,
    BacktestCostConfig,
    BacktestExecutionConfig,
    CostMode,
)
from app.backtest.engine import BacktestEngine
from app.backtest.schemas import TradeLifecycle
from app.backtest.simulator import TradeSimulator
from app.market.schemas import OHLCVBar, Timeframe
from app.strategy.schemas import (
    EntryZone,
    MarketContext,
    SignalDirection,
    SignalStatus,
    StrategyAnalyzeResult,
    TakeProfitLevel,
)
from app.strategy.config import StrategyConfig


def _bars(n: int = 120, start: Optional[datetime] = None) -> List[OHLCVBar]:
    t0 = start or datetime(2024, 1, 1, tzinfo=timezone.utc)
    out = []
    price = 2000.0
    for i in range(n):
        o = price
        h = price + 2
        l = price - 2
        c = price + 0.5
        out.append(
            OHLCVBar(
                timestamp=t0 + timedelta(minutes=15 * i),
                symbol="XAUUSD",
                timeframe=Timeframe.M15,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=1.0,
                source="test",
            )
        )
        price = c
    return out


def _signal_result(
    *,
    direction: SignalDirection,
    score: int,
    entry: float,
    sl: float,
    tp: float,
    symbol: str = "XAUUSD",
) -> StrategyAnalyzeResult:
    return StrategyAnalyzeResult(
        symbol=symbol,
        as_of="2024-01-01T00:00:00+00:00",
        signal=direction,
        score=score,
        score_label=f"{score}/100 strategy condition score",
        status=SignalStatus.CONFIRMED,
        signal_id="sig-fixed",
        setup_id="setup-fixed",
        entry=EntryZone(low=entry - 1, high=entry + 1, preferred=entry),
        stop_loss=sl,
        targets=[TakeProfitLevel(price=tp, rr=2.0, label="TP1")],
        primary_rr=2.0,
        market_context=MarketContext(
            htf_bias="BULLISH",
            setup_bias="BULLISH",
            entry_bias="BULLISH",
            state="TRENDING",
        ),
        strategy_version="1.0.0",
        config=StrategyConfig(),
        reasons=["test"],
        risks=[],
    )


@pytest.fixture
def stub_buy(monkeypatch: pytest.MonkeyPatch):
    def _analyze(self, bars_by_tf, *, symbol, as_of, timeframes=None):  # noqa: ANN001
        # Emit BUY once near start of post-warmup, else WAIT
        entry_bars = list(bars_by_tf.get("15m", []))
        if len(entry_bars) == 81:  # first post-warmup window length roughly
            last = entry_bars[-1]
            px = last.close
            return _signal_result(
                direction=SignalDirection.BUY,
                score=80,
                entry=px,
                sl=px - 5,
                tp=px + 10,
                symbol=symbol,
            )
        return StrategyAnalyzeResult(
            symbol=symbol,
            as_of=as_of.isoformat(),
            signal=SignalDirection.WAIT,
            score=40,
            score_label="40/100 strategy condition score",
            status=SignalStatus.DETECTED,
            market_context=MarketContext(
                htf_bias="NEUTRAL",
                setup_bias="NEUTRAL",
                entry_bias="NEUTRAL",
                state="NEUTRAL",
            ),
            strategy_version="1.0.0",
            config=StrategyConfig(),
        )

    monkeypatch.setattr("app.strategy.engine.StrategyEngine.analyze", _analyze)


def test_simulator_expiration() -> None:
    cfg = BacktestConfig(
        cost=BacktestCostConfig(mode=CostMode.ZERO_COST),
        execution=BacktestExecutionConfig(max_signal_age_bars=2),
    )
    sim = TradeSimulator(cfg)
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    from app.strategy.schemas import StrategyAnalyzeResult as SAR

    res = _signal_result(
        direction=SignalDirection.BUY, score=80, entry=2100, sl=2090, tp=2120
    )
    # Force entry zone away from market so it never fills
    res.entry = EntryZone(low=3000, high=3002, preferred=3001)
    bar0 = OHLCVBar(
        timestamp=t0,
        symbol="XAUUSD",
        timeframe=Timeframe.M15,
        open=2000,
        high=2001,
        low=1999,
        close=2000,
        volume=1,
        source="t",
    )
    sim.on_signal(res, bar_index=10, bar=bar0)
    assert sim.pending is not None
    for i in range(11, 15):
        bar = OHLCVBar(
            timestamp=t0 + timedelta(minutes=15 * (i - 10)),
            symbol="XAUUSD",
            timeframe=Timeframe.M15,
            open=2000,
            high=2001,
            low=1999,
            close=2000,
            volume=1,
            source="t",
        )
        sim.on_bar(i, bar, max_age=2)
    assert sim.pending is None
    assert sim.signals_expired == 1
    assert sim.trades[-1].status == TradeLifecycle.EXPIRED


def test_simulator_buy_sl_and_tp() -> None:
    cfg = BacktestConfig(cost=BacktestCostConfig(mode=CostMode.ZERO_COST))
    sim = TradeSimulator(cfg)
    t0 = datetime(2024, 1, 1, tzinfo=timezone.utc)
    res = _signal_result(
        direction=SignalDirection.BUY, score=80, entry=100, sl=95, tp=110
    )
    signal_bar = OHLCVBar(
        timestamp=t0,
        symbol="XAUUSD",
        timeframe=Timeframe.M15,
        open=100,
        high=101,
        low=99,
        close=100,
        volume=1,
        source="t",
    )
    sim.on_signal(res, bar_index=0, bar=signal_bar)
    sim.on_bar(0, signal_bar, max_age=10)
    assert sim.active is not None
    # TP bar
    tp_bar = OHLCVBar(
        timestamp=t0 + timedelta(minutes=15),
        symbol="XAUUSD",
        timeframe=Timeframe.M15,
        open=105,
        high=111,
        low=104,
        close=110,
        volume=1,
        source="t",
    )
    sim.on_bar(1, tp_bar, max_age=10)
    assert sim.active is None
    assert sim.trades[-1].status == TradeLifecycle.TP_HIT
    assert sim.trades[-1].net_r is not None and sim.trades[-1].net_r > 0


def test_leakage_future_mutation(stub_buy) -> None:
    bars = _bars(150)
    cfg = BacktestConfig(
        warmup_bars=80,
        cost=BacktestCostConfig(mode=CostMode.ZERO_COST),
        strategy_version="1.0.0",
    )
    engine = BacktestEngine(cfg)
    bars_by_tf = {"15m": bars}
    a = engine.run(bars_by_tf)

    mutated = []
    cut = bars[100].timestamp
    for b in bars:
        if b.timestamp > cut:
            mutated.append(
                b.model_copy(update={"high": b.high + 500, "close": b.close + 400})
            )
        else:
            mutated.append(b)
    b = engine.run({"15m": mutated})
    # Signals/trades decided at/before cut must match
    a_sig = [s for s in a.signals if s.bar_index <= 100]
    b_sig = [s for s in b.signals if s.bar_index <= 100]
    assert len(a_sig) == len(b_sig)
    for x, y in zip(a_sig, b_sig):
        assert x.direction == y.direction
        assert x.score == y.score


def test_reproducibility(stub_buy) -> None:
    bars = _bars(150)
    cfg = BacktestConfig(warmup_bars=80, cost=BacktestCostConfig(mode=CostMode.ZERO_COST))
    engine = BacktestEngine(cfg)
    a = engine.run({"15m": bars})
    b = engine.run({"15m": bars})
    assert a.summary == b.summary
    assert a.metrics.net_profit_r == b.metrics.net_profit_r
    assert a.data_version == b.data_version
    assert len(a.trades) == len(b.trades)


def test_append_future_data_identical_on_window(stub_buy) -> None:
    bars = _bars(150)
    extra = _bars(30, start=bars[-1].timestamp + timedelta(minutes=15))
    cfg = BacktestConfig(warmup_bars=80, cost=BacktestCostConfig(mode=CostMode.ZERO_COST))
    engine = BacktestEngine(cfg)
    end = bars[140].timestamp
    a = engine.run({"15m": bars}, end=end)
    b = engine.run({"15m": bars + extra}, end=end)
    assert a.metrics.net_profit_r == b.metrics.net_profit_r
    assert a.summary["total_signals"] == b.summary["total_signals"]
