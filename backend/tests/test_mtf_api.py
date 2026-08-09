"""MTF API tests."""

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


def test_mtf_analyze_ok(client: TestClient) -> None:
    response = client.get("/api/mtf/analyze", params={"limit": 200})
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "PAXGUSD"
    assert "timeframes" in data
    assert "higher_timeframe_bias" in data
    assert "alignment_score" in data
    assert "state" in data
    assert "BUY" not in str(data.get("state", "")).upper() or data["state"] != "BUY"
    # ensure no trade signal fields
    assert "signal" not in data


def test_mtf_invalid_timeframe(client: TestClient) -> None:
    response = client.get("/api/mtf/analyze", params={"timeframes": "5m,1h"})
    assert response.status_code == 422
