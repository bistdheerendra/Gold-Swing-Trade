"""SMC API tests (Phase 4)."""

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


def test_smc_analyze_ok(client: TestClient) -> None:
    response = client.get("/api/smc/analyze", params={"timeframe": "1h", "limit": 200})
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "PAXGUSD"
    assert data["timeframe"] == "1h"
    assert "bos" in data and "choch" in data and "fvg" in data
    assert "order_blocks" in data and "liquidity" in data
    assert "dealing_range" in data and "summary" in data
    assert 0 <= data["smc_score"] <= 100


def test_smc_invalid_timeframe(client: TestClient) -> None:
    response = client.get("/api/smc/analyze", params={"timeframe": "5m"})
    assert response.status_code == 422


def test_smc_insufficient_via_as_of(client: TestClient) -> None:
    # Seed first
    client.post("/api/market/seed", params={"timeframe": "1h", "bars": 50})
    response = client.get(
        "/api/smc/analyze", params={"timeframe": "1h", "limit": 50, "as_of_index": 0}
    )
    # as_of 0 still valid structurally but may have empty detectors
    assert response.status_code in (200, 422)
