"""Dependency wiring for market data components."""

from functools import lru_cache
from typing import Annotated, AsyncGenerator

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.market.provider import MarketDataProvider, MockMarketDataProvider
from app.market.real_provider import RealMarketDataProvider
from app.market.repository import (
    InMemoryMarketDataRepository,
    MarketDataRepository,
    PostgresMarketDataRepository,
)
from app.market.service import MarketDataService
from app.market.validator import OHLCVValidator

# Process-wide in-memory store so API ingest + query share state in memory mode
_memory_repo = InMemoryMarketDataRepository()


def _delta_base_url(settings: Settings) -> str:
    # Prefer DELTA_INDIA_BASE_URL; fall back to legacy DELTA_API_BASE_URL
    if settings.delta_india_base_url:
        return settings.delta_india_base_url
    return settings.delta_api_base_url


@lru_cache
def get_provider() -> MarketDataProvider:
    settings = get_settings()
    name = settings.market_data_provider.lower().strip().replace("-", "_")

    if name in ("delta_india", "delta", "twelvedata"):
        backend = "delta_india" if name in ("delta_india", "delta") else "twelvedata"
        return RealMarketDataProvider(
            provider=backend,  # type: ignore[arg-type]
            delta_base_url=_delta_base_url(settings),
            delta_paxgusd_symbol=settings.delta_paxgusd_symbol,
            twelvedata_base_url=settings.twelvedata_api_base_url,
            twelvedata_api_key=settings.twelvedata_api_key,
        )

    if name == "mock":
        if not settings.allow_mock_data:
            raise ValueError(
                "MARKET_DATA_PROVIDER=mock is blocked for the running app. "
                "Set ALLOW_MOCK_DATA=true only for the pytest suite. "
                "Use MARKET_DATA_PROVIDER=delta_india (default) or twelvedata."
            )
        return MockMarketDataProvider()

    raise ValueError(
        f"Unsupported MARKET_DATA_PROVIDER={settings.market_data_provider}. "
        "Allowed: delta_india, twelvedata, mock (mock requires ALLOW_MOCK_DATA=true)"
    )


def get_validator() -> OHLCVValidator:
    return OHLCVValidator()


def get_memory_repository() -> InMemoryMarketDataRepository:
    return _memory_repo


async def get_market_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[MarketDataRepository, None]:
    store = settings.market_data_store.lower()
    if store == "memory":
        yield _memory_repo
        return
    if store == "postgres":
        async for session in get_db_session():
            yield PostgresMarketDataRepository(session)
            return
    raise ValueError(
        f"Unsupported MARKET_DATA_STORE={settings.market_data_store}. "
        "Allowed: memory, postgres"
    )


async def get_market_service(
    provider: Annotated[MarketDataProvider, Depends(get_provider)],
    repository: Annotated[MarketDataRepository, Depends(get_market_repository)],
    validator: Annotated[OHLCVValidator, Depends(get_validator)],
) -> MarketDataService:
    return MarketDataService(provider=provider, repository=repository, validator=validator)


def reset_market_singletons() -> None:
    """Test helper — clears provider cache and memory repository."""
    get_provider.cache_clear()
    _memory_repo._bars.clear()
