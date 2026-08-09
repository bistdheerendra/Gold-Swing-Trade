"""Phase 11 — instrument / risk / sizing / margin / costs / guards."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.instruments.paxgusd import PAXGUSD_SPEC
from app.instruments.registry import DEFAULT_INSTRUMENT, get_instrument
from app.instruments.validation import validate_stop_loss, validate_targets
from app.main import app
from app.risk.config import AccountRiskConfig, FundingCostMode, SpreadSource
from app.risk.costs import estimate_costs
from app.risk.engine import RiskEngine
from app.risk.guards import DailyRiskState, check_daily_and_streak
from app.risk.margin import check_margin
from app.risk.schemas import RiskStatus
from app.risk.sizing import size_position
from app.risk.store import reset_risk_config
from app.strategy.schemas import SignalDirection, TakeProfitLevel
from app.core.config import get_settings
from app.market.deps import reset_market_singletons


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_DATA_STORE", "memory")
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_MOCK_DATA", "true")
    monkeypatch.setenv("STRATEGY_VERSION", "1.0.0")
    monkeypatch.setenv("MARKET_SYMBOL", "PAXGUSD")
    get_settings.cache_clear()
    reset_market_singletons()
    reset_risk_config()
    yield
    reset_risk_config()
    reset_market_singletons()
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_default_instrument_paxgusd() -> None:
    assert DEFAULT_INSTRUMENT == "PAXGUSD"
    spec = get_instrument("PAXGUSD")
    assert spec.contract_size == 0.001
    assert spec.tick_size == 0.01
    assert spec.quantity_step == 1.0
    assert spec.verification.value == "VERIFIED_API"


def test_paxgusd_symbol_validation() -> None:
    with pytest.raises(ValueError):
        get_instrument("FAKEUSD")


def test_entry_sl_buy_sell() -> None:
    instr = PAXGUSD_SPEC
    ok = validate_stop_loss(
        direction=SignalDirection.BUY,
        entry=4340.0,
        stop_loss=4330.0,
        instrument=instr,
        min_stop_distance=0.05,
        max_stop_distance_pct=5.0,
    )
    assert ok.ok and ok.stop_distance == 10.0
    bad = validate_stop_loss(
        direction=SignalDirection.BUY,
        entry=4340.0,
        stop_loss=4350.0,
        instrument=instr,
    )
    assert not bad.ok


def test_invalid_sl_equals_entry() -> None:
    r = validate_stop_loss(
        direction=SignalDirection.BUY,
        entry=4340.0,
        stop_loss=4340.0,
        instrument=PAXGUSD_SPEC,
    )
    assert not r.ok


def test_tp_validation_order() -> None:
    targets = [
        TakeProfitLevel(price=4350, rr=1, label="TP1"),
        TakeProfitLevel(price=4360, rr=2, label="TP2"),
        TakeProfitLevel(price=4370, rr=3, label="TP3"),
    ]
    assert validate_targets(
        direction=SignalDirection.BUY, entry=4340.0, targets=targets
    ).ok
    bad = [
        TakeProfitLevel(price=4370, rr=1, label="TP1"),
        TakeProfitLevel(price=4350, rr=2, label="TP2"),
        TakeProfitLevel(price=4360, rr=3, label="TP3"),
    ]
    assert not validate_targets(
        direction=SignalDirection.BUY, entry=4340.0, targets=bad
    ).ok


def test_position_sizing_buy_risk_percent() -> None:
    acct = AccountRiskConfig(account_balance=30_000, risk_per_trade_pct=1.0, usd_inr_rate=83.0)
    # risk INR 300 → ~$3.614; loss/contract = 0.001 * 10 = 0.01 → qty ~361
    sized = size_position(
        instrument=PAXGUSD_SPEC, account=acct, entry=4340.0, stop_distance=10.0
    )
    assert sized.ok
    assert sized.rounded_quantity >= 1
    assert sized.notional_usd > 0
    assert sized.raw_quantity >= sized.rounded_quantity


def test_sell_sizing() -> None:
    acct = AccountRiskConfig(account_balance=10_000, risk_per_trade_pct=1.0)
    sized = size_position(
        instrument=PAXGUSD_SPEC, account=acct, entry=4340.0, stop_distance=15.0
    )
    assert sized.ok or sized.rounded_quantity == 0


def test_quantity_rounding_min_max() -> None:
    acct = AccountRiskConfig(account_balance=50.0, risk_per_trade_pct=0.5, usd_inr_rate=83.0)
    tiny = size_position(
        instrument=PAXGUSD_SPEC, account=acct, entry=4340.0, stop_distance=50.0
    )
    assert not tiny.ok  # below minimum


def test_notional_and_margin() -> None:
    acct = AccountRiskConfig(account_balance=30_000, default_leverage=5.0)
    sized = size_position(
        instrument=PAXGUSD_SPEC, account=acct, entry=4340.0, stop_distance=10.0
    )
    m = check_margin(
        instrument=PAXGUSD_SPEC,
        account=acct,
        notional_usd=sized.notional_usd,
        leverage=5.0,
    )
    assert m.required_margin_usd == pytest.approx(sized.notional_usd / 5.0, rel=1e-6)


def test_insufficient_margin() -> None:
    acct = AccountRiskConfig(
        account_balance=500.0,
        available_balance=500.0,
        default_leverage=2.0,
        maximum_leverage=2.0,
        minimum_margin_buffer_pct=50.0,
        max_total_exposure_pct=100.0,
    )
    m = check_margin(
        instrument=PAXGUSD_SPEC,
        account=acct,
        notional_usd=10_000.0,
        leverage=2.0,
    )
    assert not m.ok
    assert not m.buffer_ok


def test_position_limit() -> None:
    acct = AccountRiskConfig(
        account_balance=10_000,
        currency="USD",
        max_total_exposure_pct=10.0,
        minimum_margin_buffer_pct=0.0,
    )
    # margin = 6000/5 = 1200 > 10% of 10k (=1000)
    m = check_margin(
        instrument=PAXGUSD_SPEC, account=acct, notional_usd=6_000.0, leverage=5.0
    )
    assert not m.exposure_ok


def test_risk_accepted_path() -> None:
    # USD research account; modest risk so margin fits exposure buffer
    acct = AccountRiskConfig(
        account_balance=30_000,
        currency="USD",
        risk_per_trade_pct=0.5,
        default_leverage=5.0,
        maximum_leverage=20.0,
        minimum_rr=0.1,
        max_stop_distance_pct=10.0,
        min_stop_ticks=1,
        max_total_exposure_pct=90.0,
        minimum_margin_buffer_pct=5.0,
    )
    engine = RiskEngine(acct)
    plan = engine.build_plan(
        symbol="PAXGUSD",
        direction=SignalDirection.BUY,
        entry=4340.0,
        stop_loss=4320.0,  # $20 stop → smaller size
        targets=[
            TakeProfitLevel(price=4380, rr=2, label="TP1"),
            TakeProfitLevel(price=4400, rr=3, label="TP2"),
            TakeProfitLevel(price=4420, rr=4, label="TP3"),
        ],
        account=acct,
        leverage=5.0,
    )
    assert plan.risk_status == RiskStatus.RISK_ACCEPTED, plan.reasons
    assert plan.gross_rr is not None
    assert plan.net_rr is not None
    assert plan.net_rr <= plan.gross_rr + 1e-9
    assert plan.quantity >= 1


def test_min_rr_reject() -> None:
    acct = AccountRiskConfig(
        account_balance=30_000,
        currency="USD",
        risk_per_trade_pct=0.5,
        minimum_rr=50.0,
        max_stop_distance_pct=10.0,
        min_stop_ticks=1,
        max_total_exposure_pct=90.0,
        minimum_margin_buffer_pct=5.0,
    )
    plan = RiskEngine(acct).build_plan(
        symbol="PAXGUSD",
        direction=SignalDirection.BUY,
        entry=4340.0,
        stop_loss=4320.0,
        targets=[TakeProfitLevel(price=4345, rr=0.25, label="TP1")],
        account=acct,
        leverage=5.0,
    )
    assert plan.risk_status == RiskStatus.RISK_REJECTED, plan.reasons


def test_costs_spread_slippage_fees_funding_unknown() -> None:
    acct = AccountRiskConfig(
        funding_mode=FundingCostMode.UNKNOWN,
        spread_source=SpreadSource.CONFIGURED,
        estimated_spread=0.5,
    )
    c = estimate_costs(
        instrument=PAXGUSD_SPEC, account=acct, entry=4340.0, quantity=100.0
    )
    assert c.funding_cost == 0.0
    assert c.funding_mode == FundingCostMode.UNKNOWN
    assert c.spread_cost > 0
    assert c.trading_fee > 0
    assert "UNKNOWN" in " ".join(c.notes)


def test_daily_and_streak_guards() -> None:
    acct = AccountRiskConfig(max_daily_loss_pct=3.0, max_consecutive_losses=3)
    blocked = check_daily_and_streak(
        acct,
        DailyRiskState(starting_daily_equity=30_000, realized_pnl=-1000, consecutive_losses=0),
    )
    assert blocked.status == "DAILY_LIMIT_REACHED"
    streak = check_daily_and_streak(
        acct,
        DailyRiskState(starting_daily_equity=30_000, consecutive_losses=3),
    )
    assert streak.status == "TRADING_BLOCKED"


def test_wait_never_becomes_buy() -> None:
    engine = RiskEngine(AccountRiskConfig())
    plan = engine.build_plan(
        symbol="PAXGUSD",
        direction=SignalDirection.WAIT,
        entry=4340.0,
        stop_loss=4330.0,
        targets=[TakeProfitLevel(price=4360, rr=2, label="TP1")],
        account=AccountRiskConfig(),
    )
    assert plan.risk_status == RiskStatus.SKIPPED_NO_SIGNAL
    assert plan.quantity == 0


def test_invalid_leverage() -> None:
    acct = AccountRiskConfig(maximum_leverage=5.0)
    m = check_margin(
        instrument=PAXGUSD_SPEC, account=acct, notional_usd=100.0, leverage=100.0
    )
    assert not m.leverage_ok


def test_api_config_and_analyze(client: TestClient) -> None:
    cfg = client.get("/api/risk/config")
    assert cfg.status_code == 200
    assert cfg.json()["default_instrument"] == "PAXGUSD"
    r = client.get(
        "/api/risk/analyze",
        params={
            "symbol": "PAXGUSD",
            "account_balance": 30000,
            "risk_percent": 1.0,
            "leverage": 5,
            "minimum_rr": 0.01,
            "mode": "RULE_ONLY",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "trade_plan" in body
    assert body["trade_plan"]["instrument"] == "PAXGUSD"
    # WAIT path common on mock — must not invent BUY from WAIT
    if body["trade_plan"]["signal_status"] in ("WAIT", "NO_TRADE"):
        assert body["trade_plan"]["risk_status"] == "SKIPPED_NO_SIGNAL"


def test_api_backtest_risk_percent(client: TestClient) -> None:
    r = client.post(
        "/api/risk/backtest",
        json={
            "symbol": "PAXGUSD",
            "risk_mode": "RISK_PERCENT",
            "risk_fraction_per_trade": 0.01,
            "initial_equity": 30000,
            "limit": 220,
            "warmup_bars": 80,
            "signal_mode": "RULE_ONLY",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "loss_streaks" in data
    assert data["ruin_estimate"]["label"].startswith("RESEARCH")
    assert "RISK_PERCENT" in " ".join(data["notes"])


def test_health_phase_11(client: TestClient) -> None:
    assert client.get("/api/health").json()["phase"] == 11.5
    assert client.get("/").json()["phase"] == "11.5"


def test_no_place_order_on_broker() -> None:
    from app.risk.broker import MockBrokerAdapter

    assert not hasattr(MockBrokerAdapter, "place_order")
    assert not hasattr(MockBrokerAdapter, "cancel_order")


def test_funding_not_invented_when_unknown() -> None:
    acct = AccountRiskConfig(funding_mode=FundingCostMode.UNKNOWN)
    c = estimate_costs(
        instrument=PAXGUSD_SPEC, account=acct, entry=4340.0, quantity=10.0
    )
    assert c.funding_cost == 0.0


def test_tick_size_rounding() -> None:
    assert PAXGUSD_SPEC.round_price(4340.014) == 4340.01
    assert PAXGUSD_SPEC.round_quantity(12.9) == 12.0
