"""ML dataset API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.market.deps import reset_market_singletons
from app.ml.dataset_builder import clear_datasets


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MARKET_DATA_STORE", "memory")
    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_MOCK_DATA", "true")
    get_settings.cache_clear()
    reset_market_singletons()
    clear_datasets()
    yield
    clear_datasets()
    reset_market_singletons()
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_ml_dataset_build(client: TestClient) -> None:
    response = client.post(
        "/api/ml/dataset/build",
        json={
            "symbol": "XAUUSD",
            "timeframe": "15m",
            "limit": 220,
            "warmup_bars": 80,
            "row_step": 4,
            "include_strategy": False,
            "feature_version": "1.0.0",
            "label_version": "1.0.0",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["metadata"]["row_count"] > 0
    assert data["statistics"]["feature_count"] > 10
    assert "preview_rows" in data
    did = data["dataset_id"]
    assert client.get(f"/api/ml/dataset/{did}").status_code == 200
    assert client.get(f"/api/ml/dataset/{did}/stats").status_code == 200


def test_health_phase_11(client: TestClient) -> None:
    assert client.get("/api/health").json()["phase"] == 11.5
    assert client.get("/").json()["phase"] == "11.5"
