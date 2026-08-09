"""Market data application service."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from app.core.errors import ValidationAppError
from app.core.logging import get_logger
from app.market.provider import MarketDataProvider, default_range_for_timeframe
from app.market.repository import MarketDataRepository
from app.market.schemas import (
    OHLCVBar,
    OHLCVQuery,
    Timeframe,
    ValidationReport,
    parse_timeframe,
    sort_bars,
)
from app.market.validator import OHLCVValidator, clip_to_range

logger = get_logger(__name__)


class MarketDataService:
    """
    Orchestrates provider → validate → store → query.

    Does not embed strategy logic. Does not fabricate missing candles.
    """

    def __init__(
        self,
        provider: MarketDataProvider,
        repository: MarketDataRepository,
        validator: Optional[OHLCVValidator] = None,
        *,
        reject_on_missing: bool = False,
    ) -> None:
        self.provider = provider
        self.repository = repository
        self.validator = validator or OHLCVValidator()
        self.reject_on_missing = reject_on_missing

    async def ingest_historical(
        self,
        symbol: str,
        timeframe: str | Timeframe,
        start: datetime,
        end: datetime,
        *,
        persist: bool = True,
    ) -> tuple[List[OHLCVBar], ValidationReport]:
        tf = timeframe if isinstance(timeframe, Timeframe) else parse_timeframe(timeframe)
        try:
            raw = await self.provider.get_historical_ohlcv(symbol, tf, start, end)
        except Exception as exc:  # noqa: BLE001 — never silent-fallback to mock
            logger.error(
                "provider_fetch_failed symbol=%s timeframe=%s provider=%s err=%s",
                symbol,
                tf.value if hasattr(tf, "value") else tf,
                getattr(self.provider, "name", type(self.provider).__name__),
                exc,
            )
            raise ValidationAppError(
                f"Market data provider failed (no mock fallback): {exc}"
            ) from exc
        # Clip without sorting so chronological defects from the provider remain visible
        clipped = clip_to_range(raw, start, end, sort=False)

        report = self.validator.validate(
            clipped,
            expect_symbol=symbol,
            expect_timeframe=tf,
            check_missing=True,
        )

        if report.has_blocking_errors:
            raise ValidationAppError(
                "OHLCV validation failed: "
                + "; ".join(f"{i.code}: {i.message}" for i in report.issues[:5])
            )

        if self.reject_on_missing and report.missing_timestamps:
            raise ValidationAppError(
                f"Missing {len(report.missing_timestamps)} candles in requested range"
            )

        bars = sort_bars(clipped)
        if persist and bars:
            saved = await self.repository.upsert_bars(bars)
            logger.info(
                "ingested_ohlcv symbol=%s timeframe=%s bars=%s saved=%s source=%s",
                symbol,
                tf.value,
                len(bars),
                saved,
                self.provider.name,
            )

        return bars, report

    async def get_ohlcv(self, query: OHLCVQuery) -> List[OHLCVBar]:
        return await self.repository.get_bars(
            symbol=query.symbol,
            timeframe=query.timeframe,
            start=query.start,
            end=query.end,
            limit=query.limit,
        )

    async def ensure_sample_data(
        self,
        symbol: str,
        timeframe: str | Timeframe,
        *,
        bars: int = 300,
        force: bool = False,
    ) -> tuple[List[OHLCVBar], ValidationReport]:
        """
        Ensure OHLCV history exists from the active provider.
        force=True clears store and re-fetches (live refresh for delta).
        """
        tf = timeframe if isinstance(timeframe, Timeframe) else parse_timeframe(timeframe)
        existing = await self.repository.count_bars(symbol, tf)
        if existing > 0 and not force:
            stored = await self.repository.get_bars(symbol, tf, limit=bars)
            report = self.validator.validate(
                stored,
                expect_symbol=symbol,
                expect_timeframe=tf,
                check_missing=False,
            )
            return stored, report

        if force and existing > 0:
            await self.repository.clear(symbol=symbol, timeframe=tf)

        start, end = default_range_for_timeframe(tf, bars=bars)
        return await self.ingest_historical(symbol, tf, start, end, persist=True)

    async def refresh_ohlcv(
        self,
        symbol: str,
        timeframe: str | Timeframe,
        *,
        bars: int = 400,
    ) -> tuple[List[OHLCVBar], ValidationReport]:
        """Force re-ingest latest window from the configured provider."""
        return await self.ensure_sample_data(symbol, timeframe, bars=bars, force=True)
