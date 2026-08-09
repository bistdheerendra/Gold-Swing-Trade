"""Market data repositories — memory + PostgreSQL."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.market.schemas import OHLCVBar, Timeframe, ensure_utc, sort_bars
from app.models.ohlcv import OHLCVBarModel


class MarketDataRepository(ABC):
    """Persistence port for normalized OHLCV bars."""

    @abstractmethod
    async def upsert_bars(self, bars: List[OHLCVBar]) -> int:
        """Insert or update bars. Returns number of rows touched."""

    @abstractmethod
    async def get_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[OHLCVBar]:
        """Return bars ascending by timestamp, clipped to [start, end]."""

    @abstractmethod
    async def count_bars(self, symbol: str, timeframe: Timeframe) -> int:
        pass

    @abstractmethod
    async def clear(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[Timeframe] = None,
    ) -> int:
        pass


class InMemoryMarketDataRepository(MarketDataRepository):
    """Process-local store for tests and Docker-free development."""

    def __init__(self) -> None:
        self._bars: Dict[Tuple[str, str, datetime], OHLCVBar] = {}

    async def upsert_bars(self, bars: List[OHLCVBar]) -> int:
        touched = 0
        for bar in bars:
            key = (bar.symbol, bar.timeframe.value, ensure_utc(bar.timestamp))
            self._bars[key] = bar.model_copy(deep=True)
            touched += 1
        return touched

    async def get_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[OHLCVBar]:
        symbol_u = symbol.upper()
        start_utc = ensure_utc(start) if start else None
        end_utc = ensure_utc(end) if end else None
        rows: List[OHLCVBar] = []
        for (sym, tf, ts), bar in self._bars.items():
            if sym != symbol_u or tf != timeframe.value:
                continue
            if start_utc and ts < start_utc:
                continue
            if end_utc and ts > end_utc:
                continue
            rows.append(bar)
        ordered = sort_bars(rows)
        if limit is not None:
            return ordered[-limit:] if limit else ordered
        return ordered

    async def count_bars(self, symbol: str, timeframe: Timeframe) -> int:
        symbol_u = symbol.upper()
        return sum(
            1
            for (sym, tf, _) in self._bars
            if sym == symbol_u and tf == timeframe.value
        )

    async def clear(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[Timeframe] = None,
    ) -> int:
        if symbol is None and timeframe is None:
            count = len(self._bars)
            self._bars.clear()
            return count
        symbol_u = symbol.upper() if symbol else None
        tf_value = timeframe.value if timeframe else None
        keys = [
            key
            for key in self._bars
            if (symbol_u is None or key[0] == symbol_u)
            and (tf_value is None or key[1] == tf_value)
        ]
        for key in keys:
            del self._bars[key]
        return len(keys)


class PostgresMarketDataRepository(MarketDataRepository):
    """PostgreSQL-backed OHLCV store using upsert on unique (symbol, timeframe, timestamp)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_bars(self, bars: List[OHLCVBar]) -> int:
        if not bars:
            return 0
        now = datetime.now(timezone.utc)
        rows = [
            {
                "symbol": bar.symbol,
                "timeframe": bar.timeframe.value,
                "timestamp": ensure_utc(bar.timestamp),
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
                "source": bar.source,
                "created_at": now,
            }
            for bar in bars
        ]
        stmt = pg_insert(OHLCVBarModel).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_ohlcv_symbol_tf_ts",
            set_={
                "open": stmt.excluded.open,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "close": stmt.excluded.close,
                "volume": stmt.excluded.volume,
                "source": stmt.excluded.source,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()
        return len(rows)

    async def get_bars(
        self,
        symbol: str,
        timeframe: Timeframe,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[OHLCVBar]:
        conditions = [
            OHLCVBarModel.symbol == symbol.upper(),
            OHLCVBarModel.timeframe == timeframe.value,
        ]
        if start is not None:
            conditions.append(OHLCVBarModel.timestamp >= ensure_utc(start))
        if end is not None:
            conditions.append(OHLCVBarModel.timestamp <= ensure_utc(end))

        stmt = (
            select(OHLCVBarModel)
            .where(and_(*conditions))
            .order_by(OHLCVBarModel.timestamp.asc())
        )
        if limit is not None:
            # Latest N within filter: subquery pattern via reverse+limit then re-sort
            stmt = (
                select(OHLCVBarModel)
                .where(and_(*conditions))
                .order_by(OHLCVBarModel.timestamp.desc())
                .limit(limit)
            )
            result = await self._session.execute(stmt)
            models = list(reversed(result.scalars().all()))
        else:
            result = await self._session.execute(stmt)
            models = list(result.scalars().all())

        return [_to_schema(model) for model in models]

    async def count_bars(self, symbol: str, timeframe: Timeframe) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(OHLCVBarModel)
            .where(
                OHLCVBarModel.symbol == symbol.upper(),
                OHLCVBarModel.timeframe == timeframe.value,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def clear(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[Timeframe] = None,
    ) -> int:
        conditions = []
        if symbol is not None:
            conditions.append(OHLCVBarModel.symbol == symbol.upper())
        if timeframe is not None:
            conditions.append(OHLCVBarModel.timeframe == timeframe.value)
        stmt = delete(OHLCVBarModel)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        result = await self._session.execute(stmt)
        await self._session.commit()
        return int(result.rowcount or 0)


def _to_schema(model: OHLCVBarModel) -> OHLCVBar:
    return OHLCVBar(
        timestamp=ensure_utc(model.timestamp),
        symbol=model.symbol,
        timeframe=Timeframe(model.timeframe),
        open=float(model.open),
        high=float(model.high),
        low=float(model.low),
        close=float(model.close),
        volume=float(model.volume),
        source=model.source,
    )
