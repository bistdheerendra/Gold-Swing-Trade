"""Backtest API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.backtest.engine import clear_results
from app.core.config import get_settings
from app.main import app
from app.market.deps import reset_market_singletons


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_DATA_STORE", "memory")
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_MOCK_DATA", "true")
    monkeypatch.setenv("STRATEGY_VERSION", "1.0.0")
    get_settings.cache_clear()
    reset_market_singletons()
    clear_results()
    yield
    clear_results()
    reset_market_singletons()
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_backtest_run_ok(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import datetime, timezone

    from app.strategy.config import StrategyConfig
    from app.strategy.schemas import (
        MarketContext,
        SignalDirection,
        SignalStatus,
        StrategyAnalyzeResult,
    )

    def _analyze(self, bars_by_tf, *, symbol, as_of, timeframes=None):  # noqa: ANN001
        return StrategyAnalyzeResult(
            symbol=symbol,
            as_of=as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of),
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

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "XAUUSD",
            "timeframe": "15m",
            "limit": 200,
            "warmup_bars": 80,
            "initial_equity": 100000,
            "cost_config": {"mode": "ZERO_COST"},
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "backtest_id" in data
    assert "metrics" in data
    assert "equity_curve" in data
    assert data["strategy_version"] == "1.0.0"

    bid = data["backtest_id"]
    got = client.get(f"/api/backtest/{bid}")
    assert got.status_code == 200
    trades = client.get(f"/api/backtest/{bid}/trades")
    assert trades.status_code == 200


def test_backtest_invalid_timeframe(client: TestClient) -> None:
    response = client.post(
        "/api/backtest/run",
        json={"timeframe": "5m", "limit": 200},
    )
    assert response.status_code == 422


def test_backtest_invalid_dates(client: TestClient) -> None:
    response = client.post(
        "/api/backtest/run",
        json={
            "timeframe": "15m",
            "start": "2024-06-01T00:00:00Z",
            "end": "2024-01-01T00:00:00Z",
            "limit": 200,
        },
    )
    assert response.status_code == 422


def test_health_phase_11(client: TestClient) -> None:
    assert client.get("/api/health").json()["phase"] == 11.5
    assert client.get("/").json()["phase"] == "11.5"
