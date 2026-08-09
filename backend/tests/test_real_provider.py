"""Tests for RealMarketDataProvider — Delta India + Twelve Data."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.market.real_provider import RealMarketDataProvider
from app.market.schemas import Timeframe


def test_twelvedata_requires_api_key() -> None:
    with pytest.raises(ValueError, match="TWELVEDATA_API_KEY"):
        RealMarketDataProvider(provider="twelvedata", twelvedata_api_key="")


def test_delta_symbol_map_paxgusd_only() -> None:
    p = RealMarketDataProvider(provider="delta_india", delta_paxgusd_symbol="PAXGUSD")
    assert p.map_symbol("PAXGUSD") == "PAXGUSD"
    with pytest.raises(ValueError, match="PAXGUSD only"):
        p.map_symbol("XAUUSD")


@pytest.mark.asyncio
async def test_delta_rejects_malformed_ohlc_row() -> None:
    start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 6, 1, 3, 0, tzinfo=timezone.utc)
    bad = {
        "time": int(start.timestamp()),
        "open": 100.0,
        "high": 90.0,
        "low": 95.0,
        "close": 98.0,
        "volume": 1.0,
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "result": [bad]}
    mock_resp.headers = {}

    provider = RealMarketDataProvider(
        provider="delta_india", min_request_interval_seconds=0.0
    )
    with patch.object(provider, "ensure_delta_symbol_verified", new_callable=AsyncMock) as v:
        v.return_value = "PAXGUSD"
        with patch(
            "app.market.real_provider._request_with_backoff", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = mock_resp
            with pytest.raises(RuntimeError, match="Invalid OHLC|Rejecting malformed"):
                await provider.get_historical_ohlcv("PAXGUSD", Timeframe.H1, start, end)


@pytest.mark.asyncio
async def test_delta_accepts_valid_candles() -> None:
    start = datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc)
    rows = []
    price = 2300.0
    for i in range(4):
        ts = start + timedelta(hours=i)
        o = price
        c = price + 1.0
        rows.append(
            {
                "time": int(ts.timestamp()),
                "open": o,
                "high": c + 0.5,
                "low": o - 0.5,
                "close": c,
                "volume": 10.0,
            }
        )
        price = c
    end = start + timedelta(hours=3)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True, "result": rows}
    mock_resp.headers = {}

    provider = RealMarketDataProvider(
        provider="delta_india", min_request_interval_seconds=0.0
    )
    with patch.object(provider, "ensure_delta_symbol_verified", new_callable=AsyncMock) as v:
        v.return_value = "PAXGUSD"
        with patch(
            "app.market.real_provider._request_with_backoff", new_callable=AsyncMock
        ) as mock_req:
            mock_req.return_value = mock_resp
            bars = await provider.get_historical_ohlcv(
                "PAXGUSD", Timeframe.H1, start, end
            )

    assert len(bars) == 4
    assert bars[0].symbol == "PAXGUSD"
    assert bars[0].source == "real_delta_india"
    assert all(b.timeframe == Timeframe.H1 for b in bars)


@pytest.mark.asyncio
async def test_delta_supports_30m_resolution_mapping() -> None:
    provider = RealMarketDataProvider(provider="delta_india")
    from app.market.real_provider import _DELTA_RESOLUTION

    assert _DELTA_RESOLUTION[Timeframe.M30] == "30m"


@pytest.mark.asyncio
async def test_twelvedata_rejects_error_payload() -> None:
    start = datetime(2024, 6, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": "error",
        "code": 401,
        "message": "Invalid API key",
    }
    mock_resp.headers = {}

    provider = RealMarketDataProvider(
        provider="twelvedata",
        twelvedata_api_key="test-key",
        min_request_interval_seconds=0.0,
    )
    with patch(
        "app.market.real_provider._request_with_backoff", new_callable=AsyncMock
    ) as mock_req:
        mock_req.return_value = mock_resp
        with pytest.raises(RuntimeError, match="Twelve Data error"):
            await provider.get_historical_ohlcv("XAUUSD", Timeframe.M30, start, end)


@pytest.mark.asyncio
async def test_no_mock_fallback_on_http_failure() -> None:
    start = datetime(2024, 6, 1, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    provider = RealMarketDataProvider(
        provider="delta_india", min_request_interval_seconds=0.0
    )
    with patch.object(provider, "ensure_delta_symbol_verified", new_callable=AsyncMock) as v:
        v.return_value = "PAXGUSD"
        with patch(
            "app.market.real_provider._request_with_backoff",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Request failed after retries"),
        ):
            with pytest.raises(RuntimeError, match="failed"):
                await provider.get_historical_ohlcv(
                    "PAXGUSD", Timeframe.H1, start, end
                )


@pytest.mark.asyncio
async def test_mock_provider_gated_without_allow_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings
    from app.market.deps import get_provider, reset_market_singletons

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_MOCK_DATA", "false")
    get_settings.cache_clear()
    reset_market_singletons()
    with pytest.raises(ValueError, match="ALLOW_MOCK_DATA"):
        get_provider()
    get_settings.cache_clear()
    reset_market_singletons()


@pytest.mark.asyncio
async def test_mock_provider_allowed_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings
    from app.market.deps import get_provider, reset_market_singletons
    from app.market.provider import MockMarketDataProvider

    monkeypatch.setenv("MARKET_DATA_PROVIDER", "mock")
    monkeypatch.setenv("ALLOW_MOCK_DATA", "true")
    get_settings.cache_clear()
    reset_market_singletons()
    provider = get_provider()
    assert isinstance(provider, MockMarketDataProvider)
    get_settings.cache_clear()
    reset_market_singletons()


@pytest.mark.asyncio
async def test_verify_delta_paxgusd_symbol_live() -> None:
    """Network smoke — skip if Delta unreachable."""
    import httpx

    from app.market.real_provider import verify_delta_paxgusd_symbol

    try:
        listed = await verify_delta_paxgusd_symbol(expected="PAXGUSD")
    except (httpx.HTTPError, RuntimeError) as exc:
        pytest.skip(f"Delta India unreachable: {exc}")
    assert listed == "PAXGUSD"
