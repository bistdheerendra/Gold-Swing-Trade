"""Supported symbols (XAUUSD + PAXGUSD)."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.market.symbols import is_supported, list_symbols, mock_base_price


def test_supported_symbols_include_paxg() -> None:
    syms = {s.symbol for s in list_symbols()}
    assert "XAUUSD" in syms
    assert "PAXGUSD" in syms
    assert is_supported("paxgusd")
    assert mock_base_price("PAXGUSD") != mock_base_price("XAUUSD")


def test_market_symbols_api() -> None:
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.get("/api/market/symbols")
    assert resp.status_code == 200
    data = resp.json()
    codes = {s["symbol"] for s in data["symbols"]}
    assert "XAUUSD" in codes and "PAXGUSD" in codes
    health = client.get("/api/health").json()
    assert "PAXGUSD" in health.get("supported_symbols", [])
