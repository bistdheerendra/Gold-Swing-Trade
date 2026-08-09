"""Health and readiness endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    """Liveness probe — process is up."""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": settings.app_name,
        "phase": 11.5,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "symbol": settings.market_symbol,
        "supported_symbols": ["XAUUSD", "PAXGUSD"],
        "market_data_provider": settings.market_data_provider,
        "allow_mock_data": settings.allow_mock_data,
        "strategy_version": settings.strategy_version,
        "model_version": settings.model_version,
    }


@router.get("/ready")
async def ready() -> dict:
    """
    Readiness probe.

    Phase 2: config + market data engine ready for charting.
    Database connectivity required only when MARKET_DATA_STORE=postgres.
    """
    settings = get_settings()
    checks = {
        "config": True,
        "market_data_provider": settings.market_data_provider,
        "market_data_store": settings.market_data_store,
        "database": (
            "required"
            if settings.market_data_store.lower() == "postgres"
            else "deferred"
        ),
        "redis": "deferred",
    }
    return {
        "status": "ready",
        "checks": checks,
        "env": settings.app_env,
    }
