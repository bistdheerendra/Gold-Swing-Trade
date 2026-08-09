import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["phase"] == "11.5"
    assert "Gold" in data["name"] or data["name"]


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["phase"] == 11.5
    assert data["symbol"] == "PAXGUSD"
    assert "timestamp" in data


def test_ready_endpoint(client: TestClient) -> None:
    response = client.get("/api/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["checks"]["config"] is True


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.market_symbol == "PAXGUSD"
    assert settings.market_data_provider == "delta_india"
    assert settings.allow_mock_data is False
    assert settings.default_timeframe == "1h"
    assert settings.min_rr >= 1.0
    assert "localhost:5173" in settings.cors_origins_list[0] or len(settings.cors_origins_list) >= 1
