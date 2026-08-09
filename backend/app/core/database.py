"""Database session helpers (Phase 0 scaffold — connection used from Phase 1)."""

from collections.abc import AsyncGenerator
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        get_engine()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session
