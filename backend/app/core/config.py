"""Central configuration — values come from environment, never hard-coded in strategy/UI."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Gold Swing AI", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    market_symbol: str = Field(default="PAXGUSD", alias="MARKET_SYMBOL")
    default_timeframe: str = Field(default="1h", alias="DEFAULT_TIMEFRAME")
    risk_percent: float = Field(default=1.0, alias="RISK_PERCENT")
    min_rr: float = Field(default=1.5, alias="MIN_RR")
    min_ml_probability: float = Field(default=0.65, alias="MIN_ML_PROBABILITY")
    max_spread: float = Field(default=0.5, alias="MAX_SPREAD")
    atr_multiplier: float = Field(default=1.5, alias="ATR_MULTIPLIER")
    strategy_version: str = Field(default="1.0.0", alias="STRATEGY_VERSION")
    model_version: str = Field(default="none", alias="MODEL_VERSION")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_user: str = Field(default="goldtrader", alias="POSTGRES_USER")
    postgres_password: str = Field(
        default="goldtrader_dev_change_me", alias="POSTGRES_PASSWORD"
    )
    postgres_db: str = Field(default="gold_swing_ai", alias="POSTGRES_DB")
    database_url: str = Field(
        default=(
            "postgresql+asyncpg://goldtrader:goldtrader_dev_change_me@"
            "localhost:5432/gold_swing_ai"
        ),
        alias="DATABASE_URL",
    )

    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Market data — Phase 11.5 real free-tier (mock only with ALLOW_MOCK_DATA=true)
    market_data_provider: str = Field(default="delta_india", alias="MARKET_DATA_PROVIDER")
    market_data_store: str = Field(default="memory", alias="MARKET_DATA_STORE")
    allow_mock_data: bool = Field(default=False, alias="ALLOW_MOCK_DATA")
    twelvedata_api_key: str = Field(default="", alias="TWELVEDATA_API_KEY")
    twelvedata_api_base_url: str = Field(
        default="https://api.twelvedata.com",
        alias="TWELVEDATA_API_BASE_URL",
    )
    # Verified against GET /v2/products — do not assume without check
    delta_india_base_url: str = Field(
        default="https://api.india.delta.exchange",
        alias="DELTA_INDIA_BASE_URL",
    )
    delta_paxgusd_symbol: str = Field(
        default="PAXGUSD",
        alias="DELTA_PAXGUSD_SYMBOL",
    )
    delta_slvonusd_symbol: str = Field(
        default="SLVONUSD",
        alias="DELTA_SLVONUSD_SYMBOL",
    )
    # Legacy alias kept for older .env files
    delta_api_base_url: str = Field(
        default="https://api.india.delta.exchange/v2",
        alias="DELTA_API_BASE_URL",
    )

    # Binance PAXGUSDT research sidecar (NOT default market provider / NOT Phase 12 GO)
    binance_futures_base_url: str = Field(
        default="https://fapi.binance.com",
        alias="BINANCE_FUTURES_BASE_URL",
    )
    binance_paxgusdt_symbol: str = Field(
        default="PAXGUSDT",
        alias="BINANCE_PAXGUSDT_SYMBOL",
    )
    binance_ml_artifacts_root: str = Field(
        default="artifacts/ml_candle_binance",
        alias="BINANCE_ML_ARTIFACTS_ROOT",
    )
    binance_ml_model_id: str = Field(
        default="",
        alias="BINANCE_ML_MODEL_ID",
    )
    binance_suggest_enabled: bool = Field(
        default=True,
        alias="BINANCE_SUGGEST_ENABLED",
    )
    # Weekly Binance research refresh (backfill + retrain) — API process scheduler
    binance_weekly_update_enabled: bool = Field(
        default=True,
        alias="BINANCE_WEEKLY_UPDATE_ENABLED",
    )
    binance_weekly_interval_days: int = Field(
        default=7,
        alias="BINANCE_WEEKLY_INTERVAL_DAYS",
    )
    binance_weekly_check_interval_sec: int = Field(
        default=3600,
        alias="BINANCE_WEEKLY_CHECK_INTERVAL_SEC",
    )
    binance_weekly_startup_delay_sec: int = Field(
        default=30,
        alias="BINANCE_WEEKLY_STARTUP_DELAY_SEC",
    )
    binance_weekly_backfill_timeout_sec: int = Field(
        default=1800,
        alias="BINANCE_WEEKLY_BACKFILL_TIMEOUT_SEC",
    )
    binance_weekly_train_timeout_sec: int = Field(
        default=3600,
        alias="BINANCE_WEEKLY_TRAIN_TIMEOUT_SEC",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
