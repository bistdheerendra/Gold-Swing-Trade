"""OHLCV persistence model."""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OHLCVBarModel(Base):
    __tablename__ = "ohlcv_bars"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "timeframe",
            "timestamp",
            name="uq_ohlcv_symbol_tf_ts",
        ),
        Index("ix_ohlcv_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
