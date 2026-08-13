"""Supported symbols (PAXGUSD + SLVONUSD; legacy XAUUSD for mock/tests)."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.instruments.registry import get_instrument, list_instruments
from app.main import app
from app.market.symbols import is_supported, list_symbols, mock_base_price


def test_supported_symbols_include_delta_metals() -> None:
    syms = {s.symbol for s in list_symbols()}
    assert "PAXGUSD" in syms
    assert "SLVONUSD" in syms
    assert "XAUUSD" in syms  # legacy mock/test reference
    assert is_supported("paxgusd")
    assert is_supported("slvonusd")
    assert mock_base_price("PAXGUSD") != mock_base_price("SLVONUSD")
    assert mock_base_price("PAXGUSD") != mock_base_price("XAUUSD")


def test_slvonusd_instrument_spec_is_independent() -> None:
    silver = get_instrument("SLVONUSD")
    gold = get_instrument("PAXGUSD")
    assert silver.contract_size == 0.1
    assert gold.contract_size == 0.001
    assert silver.funding_interval_seconds == 28800
    assert gold.funding_interval_seconds == 14400
    assert silver.maximum_quantity == 62_000.0
    codes = {i.symbol for i in list_instruments()}
    assert "SLVONUSD" in codes and "PAXGUSD" in codes


def test_market_symbols_api() -> None:
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.get("/api/market/symbols")
    assert resp.status_code == 200
    data = resp.json()
    codes = {s["symbol"] for s in data["symbols"]}
    assert "PAXGUSD" in codes and "SLVONUSD" in codes
    health = client.get("/api/health").json()
    assert health.get("phase") == "11.12"
    assert "PAXGUSD" in health.get("supported_symbols", [])
    assert "SLVONUSD" in health.get("supported_symbols", [])
