"""Gold Swing AI — FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.backtest import router as backtest_router
from app.api.combined import router as combined_router
from app.api.health import router as health_router
from app.api.market import router as market_router
from app.api.ml import router as ml_router
from app.api.mtf import router as mtf_router
from app.api.risk import router as risk_router
from app.api.smc import router as smc_router
from app.api.strategy import router as strategy_router
from app.api.ta import router as ta_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "starting_app",
        extra={
            "app_name": settings.app_name,
            "env": settings.app_env,
            "strategy_version": settings.strategy_version,
            "market_data_provider": settings.market_data_provider,
            "market_data_store": settings.market_data_store,
        },
    )
    yield
    logger.info("shutting_down_app")


app = FastAPI(
    title=settings.app_name,
    version="0.11.5",
    description=(
        "Gold Swing AI — decision-support platform for PAXGUSD research. "
        "No automatic real-money trade execution. "
        "Phase 11.5: real free-tier market data (Binance / Twelve Data)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(health_router, prefix="/api")
app.include_router(market_router, prefix="/api")
app.include_router(ta_router, prefix="/api")
app.include_router(smc_router, prefix="/api")
app.include_router(mtf_router, prefix="/api")
app.include_router(strategy_router, prefix="/api")
app.include_router(backtest_router, prefix="/api")
app.include_router(ml_router, prefix="/api")
app.include_router(combined_router, prefix="/api")
app.include_router(risk_router, prefix="/api")


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "status": "ok",
        "phase": "11.5",
        "docs": "/docs",
    }
