"""Risk Management API (Phase 11) — research only, no orders / no API keys."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.backtest.config import (
    AmbiguityPolicy,
    BacktestConfig,
    BacktestCostConfig,
    BacktestExecutionConfig,
    CostMode,
    RiskSizingMode,
    TpMode,
)
from app.backtest.data import ProviderHistoricalAdapter
from app.backtest.engine import BacktestEngine, store_result
from app.combined.config import CombinedSignalConfig, MlFallbackMode
from app.combined.engine import CombinedSignalEngine
from app.core.config import Settings, get_settings
from app.core.errors import ValidationAppError
from app.instruments.registry import DEFAULT_INSTRUMENT, get_instrument, list_instruments
from app.market.deps import get_market_service
from app.market.schemas import ANALYSIS_TIMEFRAMES, OHLCVQuery, ensure_utc, parse_timeframe
from app.market.service import MarketDataService
from app.risk.broker import get_broker_adapter, PaxgusdDataAdapter
from app.risk.config import AccountRiskConfig, FundingCostMode, SpreadSource
from app.risk.engine import RiskEngine
from app.risk.guards import DailyRiskState
from app.risk.ruin import estimate_risk_of_ruin
from app.risk.schemas import RiskAnalyzeResult, TradePlan
from app.risk.store import get_risk_config, reset_risk_config, set_risk_config
from app.risk.streaks import analyze_loss_streaks
from app.strategy.config import StrategyConfig

router = APIRouter(prefix="/risk", tags=["risk"])


class RiskAnalyzeQuery(BaseModel):
    pass


class RiskConfigUpdate(AccountRiskConfig):
    pass


class RiskBacktestRequest(BaseModel):
    symbol: str = DEFAULT_INSTRUMENT
    timeframe: str = "15m"
    initial_equity: float = 30_000.0
    risk_fraction_per_trade: float = 0.01
    risk_mode: str = "RISK_PERCENT"  # FIXED_1R | RISK_PERCENT
    signal_mode: str = "RULE_ONLY"
    model_id: Optional[str] = None
    limit: int = Field(default=400, ge=120, le=5000)
    warmup_bars: int = 80
    step: int = 1


class RiskBacktestResponse(BaseModel):
    backtest: Dict[str, Any]
    loss_streaks: Dict[str, Any]
    ruin_estimate: Dict[str, Any]
    label: str = "RESEARCH ONLY — not live execution"
    notes: List[str] = Field(default_factory=list)


@router.get("/config")
async def risk_config_get() -> Dict[str, Any]:
    cfg = get_risk_config()
    return {
        "account": cfg.model_dump(),
        "default_instrument": DEFAULT_INSTRUMENT,
        "instruments": [i.model_dump() for i in list_instruments()],
        "notes": [
            "No broker API keys stored",
            "Research settings only",
        ],
    }


@router.put("/config")
async def risk_config_put(body: RiskConfigUpdate) -> Dict[str, Any]:
    cfg = set_risk_config(body)
    return {"account": cfg.model_dump(), "status": "updated"}


@router.post("/config/reset")
async def risk_config_reset() -> Dict[str, Any]:
    cfg = reset_risk_config()
    return {"account": cfg.model_dump(), "status": "reset"}


@router.get("/instruments")
async def risk_instruments() -> Dict[str, Any]:
    return {
        "default_instrument": DEFAULT_INSTRUMENT,
        "instruments": [i.model_dump() for i in list_instruments()],
    }


@router.get("/analyze", response_model=RiskAnalyzeResult)
async def risk_analyze(
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    symbol: Optional[str] = Query(default=None),
    as_of: Optional[datetime] = Query(default=None),
    account_balance: Optional[float] = Query(default=None, gt=0),
    risk_percent: Optional[float] = Query(default=None, ge=0.01, le=10),
    leverage: Optional[float] = Query(default=None, gt=0),
    minimum_rr: Optional[float] = Query(default=None, ge=0),
    mode: str = Query(default="ML_FILTER"),
    model_id: Optional[str] = Query(default=None),
    limit: int = Query(default=500, ge=50, le=50_000),
    consecutive_losses: int = Query(default=0, ge=0),
    realized_pnl: float = Query(default=0.0),
    unrealized_pnl: float = Query(default=0.0),
) -> RiskAnalyzeResult:
    sym = (symbol or DEFAULT_INSTRUMENT).upper()
    try:
        get_instrument(sym)
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc

    as_of_utc = ensure_utc(as_of or datetime.now(timezone.utc))
    bars_by_tf: Dict[str, List] = {}
    for tf in ANALYSIS_TIMEFRAMES:
        bars = await service.get_ohlcv(
            OHLCVQuery(symbol=sym, timeframe=parse_timeframe(tf), limit=limit)
        )
        if not bars:
            bars, _ = await service.ensure_sample_data(sym, tf, bars=max(limit, 300))
        bars_by_tf[tf] = list(bars)

    acct = get_risk_config()
    updates: Dict[str, Any] = {}
    if account_balance is not None:
        updates["account_balance"] = account_balance
        updates["available_balance"] = account_balance
    if risk_percent is not None:
        updates["risk_per_trade_pct"] = risk_percent
    if leverage is not None:
        updates["default_leverage"] = leverage
    if minimum_rr is not None:
        updates["minimum_rr"] = minimum_rr
    if updates:
        acct = acct.model_copy(update=updates)

    combined = CombinedSignalEngine(
        config=CombinedSignalConfig(
            model_id=model_id,
            min_ml_confidence=0.60,
            ml_fallback=MlFallbackMode.FALLBACK_RULE,
        ),
        strategy_config=StrategyConfig(
            strategy_version=settings.strategy_version
            if settings.strategy_version not in ("", "none")
            else "1.0.0"
        ),
    )
    try:
        signal = combined.analyze(
            bars_by_tf,
            symbol=sym,
            as_of=as_of_utc,
            model_id=model_id,
            mode=mode.upper(),
        )
    except ValueError as exc:
        raise ValidationAppError(str(exc)) from exc

    broker = get_broker_adapter(
        account_balance=acct.account_balance, currency=acct.currency
    )
    ticker = await broker.get_ticker(sym)
    daily = DailyRiskState(
        starting_daily_equity=acct.account_balance,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        consecutive_losses=consecutive_losses,
    )
    engine = RiskEngine(account=acct)
    plan = engine.plan_from_combined(
        signal,
        account=acct,
        leverage=leverage if leverage is not None else acct.default_leverage,
        daily=daily,
        bid=ticker.get("bid"),
        ask=ticker.get("ask"),
    )
    plan.metadata["as_of"] = as_of_utc.isoformat()
    plan.metadata["signal_id"] = signal.signal_id
    plan.metadata["combined_direction"] = signal.direction.value
    plan.notes.append(f"spread_source from ticker: {ticker.get('spread_source')}")
    return RiskAnalyzeResult(trade_plan=plan)


@router.post("/backtest", response_model=RiskBacktestResponse)
async def risk_backtest(
    body: RiskBacktestRequest,
    service: Annotated[MarketDataService, Depends(get_market_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RiskBacktestResponse:
    try:
        risk_mode = RiskSizingMode(body.risk_mode.upper())
    except ValueError as exc:
        raise ValidationAppError("risk_mode must be FIXED_1R or RISK_PERCENT") from exc

    cfg = BacktestConfig(
        symbol=(body.symbol or DEFAULT_INSTRUMENT).upper(),
        entry_timeframe=body.timeframe,
        initial_equity=body.initial_equity,
        risk_fraction_per_trade=body.risk_fraction_per_trade,
        risk_mode=risk_mode,
        cost=BacktestCostConfig(mode=CostMode.REALISTIC_COST),
        execution=BacktestExecutionConfig(
            ambiguity_policy=AmbiguityPolicy.CONSERVATIVE,
            tp_mode=TpMode.FULL_AT_TP1,
        ),
        strategy_version=(
            settings.strategy_version
            if settings.strategy_version not in ("", "none")
            else "1.0.0"
        ),
        warmup_bars=body.warmup_bars,
        signal_mode=body.signal_mode or "RULE_ONLY",
        model_id=body.model_id,
        step=max(1, body.step),
    )
    adapter = ProviderHistoricalAdapter(service)
    bars_by_tf = {}
    for tf in ANALYSIS_TIMEFRAMES:
        bars = await adapter.load(cfg.symbol, tf, limit=body.limit)
        if not bars:
            bars, _ = await service.ensure_sample_data(cfg.symbol, tf, bars=body.limit)
        bars_by_tf[tf] = list(bars)

    engine = BacktestEngine(cfg)
    result = engine.run(bars_by_tf, split_segment="ALL")
    store_result(result)

    closed = [t for t in result.trades if t.net_r is not None]
    net_rs = [float(t.net_r or 0) for t in closed]
    net_pnls = [float(t.net_pnl or 0) for t in closed]
    streaks = analyze_loss_streaks(net_r_sequence=net_rs, net_pnl_sequence=net_pnls)
    wins = sum(1 for r in net_rs if r > 0)
    wr = wins / len(net_rs) if net_rs else 0.0
    avg_win = (
        sum(r for r in net_rs if r > 0) / max(1, wins) if wins else 1.5
    )
    losses = [r for r in net_rs if r < 0]
    avg_loss = abs(sum(losses) / len(losses)) if losses else 1.0
    ruin = estimate_risk_of_ruin(
        win_rate=wr,
        avg_win_r=avg_win,
        avg_loss_r=avg_loss,
        risk_pct=body.risk_fraction_per_trade * 100.0,
    )
    return RiskBacktestResponse(
        backtest=result.model_dump(),
        loss_streaks=streaks.model_dump(),
        ruin_estimate=ruin.model_dump(),
        notes=[
            "Uses existing Phase 7 TradeSimulator — no second execution engine",
            f"risk_mode={risk_mode.value}",
            "Do not confuse FIXED_1R normalized R with RISK_PERCENT account PnL",
            "PAXGUSD profitability is NOT claimed",
        ],
    )


@router.get("/ruin")
async def risk_ruin(
    win_rate: float = Query(default=0.5, ge=0, le=1),
    avg_win_r: float = Query(default=1.5, gt=0),
    avg_loss_r: float = Query(default=1.0, gt=0),
    risk_pct: float = Query(default=1.0, ge=0.01, le=10),
) -> Dict[str, Any]:
    return estimate_risk_of_ruin(
        win_rate=win_rate,
        avg_win_r=avg_win_r,
        avg_loss_r=avg_loss_r,
        risk_pct=risk_pct,
    ).model_dump()


@router.get("/broker/ticker")
async def broker_ticker(symbol: str = Query(default=DEFAULT_INSTRUMENT)) -> Dict[str, Any]:
    adapter = get_broker_adapter()
    return await adapter.get_ticker(symbol)


@router.get("/paxgusd/spec")
async def paxgusd_spec() -> Dict[str, Any]:
    adapter = PaxgusdDataAdapter()
    return {
        "symbol": adapter.normalize_symbol("PAXGUSD"),
        "spec": adapter.spec.model_dump(),
        "note": "Read-only research adapter — no place_order",
    }
