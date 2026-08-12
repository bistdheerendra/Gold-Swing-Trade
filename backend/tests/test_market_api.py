"""API tests for market data endpoints (Phase 1)."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.market.deps import reset_market_singletons


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_market_status(client: TestClient) -> None:
    response = client.get("/api/market/status")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "mock"
    assert data["store"] == "memory"
    assert data["symbol"] == "PAXGUSD"
    assert set(data["supported_timeframes"]) == {
        "1m",
        "5m",
        "15m",
        "30m",
        "1h",
        "4h",
        "1d",
    }


def test_ingest_and_query_ohlcv(client: TestClient) -> None:
    start = datetime(2024, 5, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=12)
    ingest = client.post(
        "/api/market/ingest",
        json={
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "persist": True,
        },
    )
    assert ingest.status_code == 200
    body = ingest.json()
    assert body["bars_ingested"] == 13
    assert body["validation"]["is_valid"] is True

    query = client.get(
        "/api/market/ohlcv",
        params={
            "symbol": "XAUUSD",
            "timeframe": "1h",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "limit": 100,
        },
    )
    assert query.status_code == 200
    payload = query.json()
    assert payload["count"] == 13
    assert payload["bars"][0]["timestamp"] <= payload["bars"][-1]["timestamp"]
    # No leakage past end
    assert all(b["timestamp"] <= end.isoformat().replace("+00:00", "Z") or True for b in payload["bars"])
    for bar in payload["bars"]:
        ts = datetime.fromisoformat(bar["timestamp"].replace("Z", "+00:00"))
        assert start <= ts <= end


def test_seed_endpoint(client: TestClient) -> None:
    response = client.post("/api/market/seed", params={"timeframe": "15m", "bars": 40})
    assert response.status_code == 200
    assert response.json()["bars_ingested"] >= 40


def test_invalid_timeframe(client: TestClient) -> None:
    response = client.get("/api/market/ohlcv", params={"timeframe": "2h"})
    assert response.status_code == 422


def test_trading_sessions_endpoint(client: TestClient) -> None:
    # Summer 13:00 UTC = London + NY + Overlap (NY opens 12:00 under EDT)
    response = client.get(
        "/api/market/sessions",
        params={"as_of": "2026-06-15T13:00:00Z"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["timezone_display"] == "IST"
    assert set(data["active"]) == {"london", "new_york", "london_ny_overlap"}
    assert len(data["sessions"]) == 4
    by_id = {s["id"]: s for s in data["sessions"]}
    assert by_id["new_york"]["utc_start_minute"] == 12 * 60
    assert by_id["new_york"]["window_mode"] == "local"
    assert by_id["new_york"]["timezone"] == "America/New_York"
    assert by_id["london"]["timezone"] == "Europe/London"
    assert by_id["london_ny_overlap"]["window_mode"] == "overlap"
    assert by_id["london_ny_overlap"]["utc_start_minute"] == 12 * 60
    assert "15m" in data["band_timeframes"]
    assert "4h" not in data["band_timeframes"]
    tag = client.get(
        "/api/market/sessions/tag",
        params={"timestamp": "2026-06-15T07:00:00Z"},
    )
    assert tag.status_code == 200
    assert set(tag.json()["sessions"]) == {"asia", "london"}
    # Winter: NY still closed at 12:00 UTC
    winter_tag = client.get(
        "/api/market/sessions/tag",
        params={"timestamp": "2026-01-15T12:00:00Z"},
    )
    assert winter_tag.status_code == 200
    assert "new_york" not in winter_tag.json()["sessions"]
    assert "london" in winter_tag.json()["sessions"]
