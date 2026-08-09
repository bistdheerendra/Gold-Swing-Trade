"""Strategy scoring, thresholds, and condition unit tests."""

from __future__ import annotations

from app.mtf.schemas import (
    BiasLabel,
    BiasWeights,
    MtfLayerSummary,
    MtfState,
    MultiTimeframeResult,
    StructureLabel,
    TimeframeAnalysis,
)
from app.smc.schemas import (
    BosEvent,
    DealingRange,
    DealingZone,
    FvgEvent,
    FvgLifecycle,
    SmcAnalysisResult,
    SmcConfig,
    SmcDirection,
    SmcEventType,
    SmcStructureSummary,
    SweepEvent,
    ZoneEvent,
)
from app.strategy.conditions import (
    DirectionalContext,
    score_buy_conditions,
    score_sell_conditions,
    total_score,
)
from app.strategy.confidence import direction_from_scores, score_band
from app.strategy.config import ScoreWeights, StrategyConfig
from app.strategy.schemas import SignalDirection


def _mtf(
    *,
    htf: BiasLabel = BiasLabel.BULLISH,
    setup: BiasLabel = BiasLabel.BULLISH,
    entry: BiasLabel = BiasLabel.BULLISH,
    state: MtfState = MtfState.TRENDING,
) -> MultiTimeframeResult:
    def layer(bias: BiasLabel, tf: str) -> MtfLayerSummary:
        return MtfLayerSummary(bias=bias, timeframe=tf, bias_score=50)

    def tf_row(tf: str, bias: BiasLabel) -> TimeframeAnalysis:
        return TimeframeAnalysis(
            timeframe=tf,
            role="x",
            trend=bias,
            structure=StructureLabel.BULLISH
            if bias == BiasLabel.BULLISH
            else StructureLabel.BEARISH
            if bias == BiasLabel.BEARISH
            else StructureLabel.NEUTRAL,
            momentum=bias,
            volatility="NORMAL",
            smc_bias=bias,
            bias_score=40 if bias == BiasLabel.BULLISH else -40 if bias == BiasLabel.BEARISH else 0,
        )

    return MultiTimeframeResult(
        symbol="XAUUSD",
        as_of="2024-01-01T00:00:00+00:00",
        timeframes={
            "1d": tf_row("1d", htf),
            "4h": tf_row("4h", htf),
            "1h": tf_row("1h", setup),
            "15m": tf_row("15m", entry),
        },
        macro=layer(htf, "1d"),
        structure=layer(htf, "4h"),
        setup=layer(setup, "1h"),
        entry=layer(entry, "15m"),
        higher_timeframe_bias=htf,
        setup_bias=setup,
        entry_bias=entry,
        alignment_score=80,
        state=state,
        weights=BiasWeights(),
    )


def _smc(
    *,
    bias: SmcDirection = SmcDirection.BULLISH,
    zone: DealingZone = DealingZone.DISCOUNT,
    with_sweep: bool = True,
    with_bos: bool = True,
    with_fvg: bool = True,
    with_ob: bool = True,
    as_of_index: int = 100,
    bullish: bool = True,
) -> SmcAnalysisResult:
    direction = SmcDirection.BULLISH if bullish else SmcDirection.BEARISH
    bos = []
    if with_bos:
        bos.append(
            BosEvent(
                id="bos:1h:90",
                type=SmcEventType.BOS,
                direction=direction,
                timeframe="1h",
                created_index=80,
                confirm_index=90,
                break_index=90,
                broken_level=2000.0,
                source_swing_index=80,
                price=2000.0,
            )
        )
    sweeps = []
    if with_sweep:
        sweeps.append(
            SweepEvent(
                id="sweep:1h:85",
                type=SmcEventType.LIQUIDITY_SWEEP,
                direction=direction,
                timeframe="1h",
                created_index=84,
                confirm_index=85,
                liquidity_level=1990.0 if bullish else 2010.0,
                sweep_index=84,
                penetration=1.0,
            )
        )
    fvgs = []
    if with_fvg:
        fvgs.append(
            FvgEvent(
                id="fvg:1h:88",
                type=SmcEventType.BULLISH_FVG if bullish else SmcEventType.BEARISH_FVG,
                direction=direction,
                timeframe="1h",
                created_index=88,
                confirm_index=88,
                high=2002.0,
                low=1998.0,
                size=4.0,
                lifecycle=FvgLifecycle.ACTIVE,
            )
        )
    obs = []
    demand = []
    supply = []
    if with_ob:
        z = ZoneEvent(
            id="ob:1h:82",
            type=SmcEventType.ORDER_BLOCK,
            direction=direction,
            timeframe="1h",
            created_index=82,
            confirm_index=90,
            high=2001.0,
            low=1995.0,
            origin_index=82,
            strength=1.0,
        )
        obs.append(z)
        if bullish:
            demand.append(z.model_copy(update={"type": SmcEventType.DEMAND_ZONE, "id": "dem:1"}))
        else:
            supply.append(z.model_copy(update={"type": SmcEventType.SUPPLY_ZONE, "id": "sup:1"}))

    return SmcAnalysisResult(
        symbol="XAUUSD",
        timeframe="1h",
        bar_count=as_of_index + 1,
        as_of_index=as_of_index,
        config=SmcConfig(),
        structure=SmcStructureSummary(bias=bias),
        bos=bos,
        fvg=fvgs,
        order_blocks=obs,
        demand_zones=demand,
        supply_zones=supply,
        liquidity_sweeps=sweeps,
        dealing_range=DealingRange(
            range_high=2050.0,
            range_low=1980.0,
            equilibrium=2015.0,
            current_price=2000.0,
            zone=zone,
        ),
    )


def test_score_band_thresholds() -> None:
    cfg = StrategyConfig()
    assert score_band(85, cfg) == "STRONG"
    assert score_band(70, cfg) == "VALID"
    assert score_band(55, cfg) == "WAIT_BAND"
    assert score_band(40, cfg) == "NO_TRADE_BAND"


def test_direction_thresholds() -> None:
    cfg = StrategyConfig()
    d, s, _ = direction_from_scores(
        buy_score=82,
        sell_score=20,
        config=cfg,
        buy_hard_block=False,
        sell_hard_block=False,
        buy_conflict=False,
        sell_conflict=False,
    )
    assert d == SignalDirection.BUY
    assert s == 82

    d, s, _ = direction_from_scores(
        buy_score=58,
        sell_score=20,
        config=cfg,
        buy_hard_block=False,
        sell_hard_block=False,
        buy_conflict=False,
        sell_conflict=False,
    )
    assert d == SignalDirection.WAIT

    d, _, _ = direction_from_scores(
        buy_score=82,
        sell_score=20,
        config=cfg,
        buy_hard_block=True,
        sell_hard_block=False,
        buy_conflict=False,
        sell_conflict=False,
    )
    assert d == SignalDirection.NO_TRADE


def test_buy_conditions_strong_setup() -> None:
    cfg = StrategyConfig()
    ctx = DirectionalContext(
        smc_4h=_smc(zone=DealingZone.DISCOUNT),
        smc_1h=_smc(zone=DealingZone.DISCOUNT),
        smc_15m=_smc(zone=DealingZone.DISCOUNT),
        mtf=_mtf(),
        as_of_index_15m=100,
    )
    # Strong bullish confluence should score as a valid setup
    conds = score_buy_conditions(ctx, cfg)
    score = total_score(conds, cfg.score_weights)
    assert score >= 65
    assert any(c.key == "liquidity_sweep" and c.met for c in conds)
    assert any(c.key == "bos_choch" and c.met for c in conds)


def test_buy_weak_without_confirmation() -> None:
    cfg = StrategyConfig()
    smc_weak = _smc(with_sweep=False, with_bos=False, with_fvg=False, with_ob=False)
    ctx = DirectionalContext(
        smc_4h=smc_weak,
        smc_1h=smc_weak,
        smc_15m=smc_weak,
        mtf=_mtf(entry=BiasLabel.BEARISH, state=MtfState.PULLBACK),
        as_of_index_15m=100,
    )
    conds = score_buy_conditions(ctx, cfg)
    score = total_score(conds, cfg.score_weights)
    assert score < 65


def test_sell_mirror() -> None:
    cfg = StrategyConfig()
    ctx = DirectionalContext(
        smc_4h=_smc(bullish=False, bias=SmcDirection.BEARISH, zone=DealingZone.PREMIUM),
        smc_1h=_smc(bullish=False, bias=SmcDirection.BEARISH, zone=DealingZone.PREMIUM),
        smc_15m=_smc(bullish=False, bias=SmcDirection.BEARISH, zone=DealingZone.PREMIUM),
        mtf=_mtf(
            htf=BiasLabel.BEARISH,
            setup=BiasLabel.BEARISH,
            entry=BiasLabel.BEARISH,
        ),
        as_of_index_15m=100,
    )
    sell = total_score(score_sell_conditions(ctx, cfg), cfg.score_weights)
    buy = total_score(score_buy_conditions(ctx, cfg), cfg.score_weights)
    assert sell >= 65
    assert sell > buy


def test_configurable_weights() -> None:
    cfg = StrategyConfig(
        score_weights=ScoreWeights(
            higher_tf_bias=50,
            structure_4h=0,
            setup_1h=0,
            liquidity_sweep=0,
            bos_choch=0,
            ob_demand_supply=0,
            fvg=0,
            premium_discount=0,
            entry_15m=50,
        )
    )
    ctx = DirectionalContext(
        smc_4h=_smc(with_sweep=False, with_bos=False, with_fvg=False, with_ob=False),
        smc_1h=_smc(with_sweep=False, with_bos=False, with_fvg=False, with_ob=False),
        smc_15m=_smc(with_sweep=False, with_bos=False, with_fvg=False, with_ob=False),
        mtf=_mtf(),
        as_of_index_15m=100,
    )
    score = total_score(score_buy_conditions(ctx, cfg), cfg.score_weights)
    # HTF + entry only → should be high
    assert score >= 80
