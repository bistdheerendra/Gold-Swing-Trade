"""API tests for /api/ta (Phase 3)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.market.deps import reset_market_singletons


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_DATA_STORE", "memory")
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_MOCK_DATA", "true")
    get_settings.cache_clear()
    reset_market_singletons()
    yield
    reset_market_singletons()
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_ta_analyze_endpoint(client: TestClient) -> None:
    response = client.get("/api/ta/analyze", params={"timeframe": "1h", "limit": 200})
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "PAXGUSD"
    assert data["timeframe"] == "1h"
    assert data["bar_count"] >= 200
    assert data["latest"]["ema_20"] is not None
    assert "structure" in data
    assert "series" in data
    assert "rsi" in data["series"]


def test_ta_invalid_timeframe(client: TestClient) -> None:
    response = client.get("/api/ta/analyze", params={"timeframe": "5m"})
    assert response.status_code == 422
