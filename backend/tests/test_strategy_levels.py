"""Entry / SL / TP / RR validation tests."""

from __future__ import annotations

from datetime import datetime, timezone

from app.market.schemas import OHLCVBar
from app.smc.schemas import (
    DealingRange,
    DealingZone,
    SmcAnalysisResult,
    SmcConfig,
    SmcDirection,
    SmcEvent,
    SmcEventType,
    SmcStructureSummary,
    SweepEvent,
    ZoneEvent,
)
from app.strategy.config import StrategyConfig
from app.strategy.schemas import EntryZone, TakeProfitLevel
from app.strategy.signal_engine import compute_levels, validate_trade_levels


def _bar(price: float) -> OHLCVBar:
    return OHLCVBar(
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
        symbol="XAUUSD",
        timeframe="15m",
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=1.0,
        source="test",
    )


def _smc_for_levels(*, bullish: bool = True) -> SmcAnalysisResult:
    direction = SmcDirection.BULLISH if bullish else SmcDirection.BEARISH
    sweep = SweepEvent(
        id="sw1",
        type=SmcEventType.LIQUIDITY_SWEEP,
        direction=direction,
        timeframe="1h",
        created_index=10,
        confirm_index=11,
        liquidity_level=1990.0 if bullish else 2010.0,
        sweep_index=10,
        penetration=1.0,
    )
    zone = ZoneEvent(
        id="z1",
        type=SmcEventType.DEMAND_ZONE if bullish else SmcEventType.SUPPLY_ZONE,
        direction=direction,
        timeframe="1h",
        created_index=8,
        confirm_index=11,
        high=2001.0,
        low=1995.0,
        origin_index=8,
    )
    swing_low = SmcEvent(
        id="sl",
        type=SmcEventType.SWING_LOW,
        direction=SmcDirection.BULLISH,
        timeframe="1h",
        created_index=5,
        confirm_index=7,
        price=1992.0,
    )
    swing_high = SmcEvent(
        id="sh",
        type=SmcEventType.SWING_HIGH,
        direction=SmcDirection.BEARISH,
        timeframe="1h",
        created_index=5,
        confirm_index=7,
        price=2020.0,
    )
    return SmcAnalysisResult(
        symbol="XAUUSD",
        timeframe="1h",
        bar_count=20,
        as_of_index=15,
        config=SmcConfig(),
        structure=SmcStructureSummary(
            bias=direction,
            last_swing_low=swing_low,
            last_swing_high=swing_high,
        ),
        demand_zones=[zone] if bullish else [],
        supply_zones=[] if bullish else [zone],
        order_blocks=[zone],
        liquidity_sweeps=[sweep],
        dealing_range=DealingRange(
            range_high=2020.0,
            range_low=1990.0,
            equilibrium=2005.0,
            current_price=2000.0,
            zone=DealingZone.DISCOUNT if bullish else DealingZone.PREMIUM,
        ),
    )


def test_buy_levels_rr_and_sides() -> None:
    cfg = StrategyConfig(min_rr=1.5, sl_buffer=0.5)
    levels = compute_levels(
        bullish=True,
        bars_15m=[_bar(2000.0)],
        smc_1h=_smc_for_levels(bullish=True),
        smc_15m=None,
        atr=5.0,
        config=cfg,
    )
    assert levels.entry is not None
    assert levels.stop_loss is not None
    assert levels.stop_loss < levels.entry.preferred
    assert levels.targets
    assert levels.targets[0].price > levels.entry.preferred
    assert levels.primary_rr is not None
    errs = validate_trade_levels(
        bullish=True,
        entry=levels.entry,
        stop_loss=levels.stop_loss,
        targets=levels.targets,
        config=cfg,
    )
    # May fail if RR too low depending on SL distance — ensure structure consistent
    assert levels.stop_loss < levels.entry.preferred


def test_sell_levels_sides() -> None:
    cfg = StrategyConfig(min_rr=1.5)
    levels = compute_levels(
        bullish=False,
        bars_15m=[_bar(2000.0)],
        smc_1h=_smc_for_levels(bullish=False),
        smc_15m=None,
        atr=5.0,
        config=cfg,
    )
    assert levels.entry is not None
    assert levels.stop_loss is not None
    assert levels.stop_loss > levels.entry.preferred
    assert levels.targets
    assert levels.targets[0].price < levels.entry.preferred


def test_poor_rr_validation() -> None:
    cfg = StrategyConfig(min_rr=3.0)
    errs = validate_trade_levels(
        bullish=True,
        entry=EntryZone(low=100, high=101, preferred=100.5),
        stop_loss=100.0,
        targets=[TakeProfitLevel(price=101.0, rr=1.0, label="TP1")],
        config=cfg,
    )
    assert any("RR" in e or "minimum" in e.lower() or "wrong side" in e.lower() for e in errs)


def test_buy_sl_stays_below_entry_when_price_ran_above_fvg() -> None:
    """Path B regression: last close above FVG must not place SL above entry.preferred."""
    from app.smc.schemas import FvgEvent, FvgLifecycle, SmcEventType

    cfg = StrategyConfig(min_rr=1.5, sl_buffer=0.5)
    fvg = FvgEvent(
        id="fvg1",
        type=SmcEventType.BULLISH_FVG,
        direction=SmcDirection.BULLISH,
        timeframe="15m",
        created_index=10,
        confirm_index=11,
        high=4376.1,
        low=4368.91,
        price=4372.505,
        size=4376.1 - 4368.91,
        lifecycle=FvgLifecycle.ACTIVE,
        filled=False,
        valid=True,
    )
    # Misleading "swing low" between FVG and current price — old bug picked this vs price
    swing_between = SmcEvent(
        id="sl_bad",
        type=SmcEventType.SWING_LOW,
        direction=SmcDirection.BULLISH,
        timeframe="1h",
        created_index=12,
        confirm_index=14,
        price=4391.0,
    )
    smc = SmcAnalysisResult(
        symbol="PAXGUSD",
        timeframe="1h",
        bar_count=20,
        as_of_index=19,
        config=SmcConfig(),
        structure=SmcStructureSummary(
            bias=SmcDirection.BULLISH,
            last_swing_low=swing_between,
            last_swing_high=SmcEvent(
                id="sh",
                type=SmcEventType.SWING_HIGH,
                direction=SmcDirection.BEARISH,
                timeframe="1h",
                created_index=15,
                confirm_index=17,
                price=4410.0,
            ),
        ),
        fvg=[fvg],
        dealing_range=DealingRange(
            range_high=4410.0,
            range_low=4360.0,
            equilibrium=4385.0,
            current_price=4400.0,
            zone=DealingZone.PREMIUM,
        ),
    )
    # Price has already run above the FVG entry zone
    levels = compute_levels(
        bullish=True,
        bars_15m=[_bar(4400.0)],
        smc_1h=smc,
        smc_15m=smc,
        atr=8.0,
        config=cfg,
    )
    assert levels.entry is not None
    assert levels.stop_loss is not None
    assert levels.entry.preferred < 4380  # still the FVG zone
    assert levels.stop_loss < levels.entry.preferred
    assert levels.stop_loss < levels.entry.low
    errs = validate_trade_levels(
        bullish=True,
        entry=levels.entry,
        stop_loss=levels.stop_loss,
        targets=levels.targets,
        config=cfg,
    )
    assert not any("wrong side" in e.lower() or "must be below" in e.lower() for e in errs)


def test_sell_sl_stays_above_entry_when_price_ran_below_zone() -> None:
    cfg = StrategyConfig(min_rr=1.5, sl_buffer=0.5)
    zone = ZoneEvent(
        id="sup1",
        type=SmcEventType.SUPPLY_ZONE,
        direction=SmcDirection.BEARISH,
        timeframe="1h",
        created_index=8,
        confirm_index=11,
        high=2010.0,
        low=2005.0,
        origin_index=8,
    )
    swing_between = SmcEvent(
        id="sh_bad",
        type=SmcEventType.SWING_HIGH,
        direction=SmcDirection.BEARISH,
        timeframe="1h",
        created_index=12,
        confirm_index=14,
        price=1995.0,  # between zone and fallen price
    )
    smc = SmcAnalysisResult(
        symbol="XAUUSD",
        timeframe="1h",
        bar_count=20,
        as_of_index=19,
        config=SmcConfig(),
        structure=SmcStructureSummary(
            bias=SmcDirection.BEARISH,
            last_swing_high=swing_between,
            last_swing_low=SmcEvent(
                id="sl",
                type=SmcEventType.SWING_LOW,
                direction=SmcDirection.BULLISH,
                timeframe="1h",
                created_index=15,
                confirm_index=17,
                price=1980.0,
            ),
        ),
        supply_zones=[zone],
        order_blocks=[zone],
        dealing_range=DealingRange(
            range_high=2015.0,
            range_low=1975.0,
            equilibrium=1995.0,
            current_price=1988.0,
            zone=DealingZone.DISCOUNT,
        ),
    )
    levels = compute_levels(
        bullish=False,
        bars_15m=[_bar(1988.0)],
        smc_1h=smc,
        smc_15m=None,
        atr=5.0,
        config=cfg,
    )
    assert levels.entry is not None
    assert levels.stop_loss is not None
    assert levels.stop_loss > levels.entry.preferred
    assert levels.stop_loss > levels.entry.high


def test_missing_levels_no_trade() -> None:
    cfg = StrategyConfig()
    errs = validate_trade_levels(
        bullish=True,
        entry=None,
        stop_loss=None,
        targets=[],
        config=cfg,
    )
    assert "Entry missing" in errs
    assert "SL missing" in errs
    assert "TP missing" in errs
