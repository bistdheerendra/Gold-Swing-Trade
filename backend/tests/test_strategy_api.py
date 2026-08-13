"""Strategy API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.market.deps import reset_market_singletons
from app.strategy.engine import reset_signal_store


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_DATA_STORE", "memory")
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_MOCK_DATA", "true")
    monkeypatch.setenv("STRATEGY_VERSION", "1.0.0")
    get_settings.cache_clear()
    reset_market_singletons()
    reset_signal_store()
    yield
    reset_signal_store()
    reset_market_singletons()
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_strategy_analyze_ok(client: TestClient) -> None:
    response = client.get("/api/strategy/analyze", params={"limit": 200})
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "PAXGUSD"
    assert data["signal"] in ("BUY", "SELL", "WAIT", "NO_TRADE")
    assert 0 <= data["score"] <= 100
    assert "strategy condition score" in data["score_label"]
    assert data["strategy_version"] == "1.0.0"
    assert "reasons" in data
    assert "risks" in data
    assert "market_context" in data
    assert "config" in data


def test_strategy_history(client: TestClient) -> None:
    client.get("/api/strategy/analyze", params={"limit": 150})
    response = client.get("/api/strategy/history", params={"limit": 20})
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "PAXGUSD"
    assert "signals" in data
    assert data["count"] == len(data["signals"])


def test_strategy_invalid_timeframe(client: TestClient) -> None:
    response = client.get("/api/strategy/analyze", params={"timeframes": "5m,1h"})
    assert response.status_code == 422


def test_health_phase_11(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["phase"] == "11.12"


def test_root_phase_11(client: TestClient) -> None:
    response = client.get("/")
    assert response.json()["phase"] == "11.12"
