"""Instrument specifications — Phase 11."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class SpecVerification(str, Enum):
    VERIFIED_API = "VERIFIED_API"
    CONFIGURED = "CONFIGURED"
    UNVERIFIED = "UNVERIFIED"


class InstrumentType(str, Enum):
    SPOT = "SPOT"
    PERPETUAL = "PERPETUAL"
    FUTURES = "FUTURES"


class InstrumentSpec(BaseModel):
    symbol: str
    base_asset: str
    quote_asset: str
    instrument_type: InstrumentType = InstrumentType.PERPETUAL
    contract_size: float = Field(
        description="Asset units per 1 quantity (Delta contract_value)"
    )
    quantity_step: float = 1.0
    minimum_quantity: float = 1.0
    maximum_quantity: float = 200_000.0
    tick_size: float = 0.01
    price_precision: int = 2
    quantity_precision: int = 0
    margin_currency: str = "USD"
    leverage_limits: List[float] = Field(
        default_factory=lambda: [1.0, 2.0, 5.0, 10.0, 20.0, 50.0]
    )
    max_leverage: float = 50.0
    default_research_leverage: float = 5.0
    maker_fee: float = 0.0001  # fraction of notional
    taker_fee: float = 0.0001
    funding_supported: bool = True
    funding_interval_seconds: Optional[int] = 14400  # 4h when known
    trading_hours: str = "24/7"
    data_source: str = "config"
    verification: SpecVerification = SpecVerification.UNVERIFIED
    verification_notes: List[str] = Field(default_factory=list)
    exchange: str = "DELTA_EXCHANGE_INDIA"

    def round_price(self, price: float) -> float:
        ticks = round(price / self.tick_size)
        return round(ticks * self.tick_size, self.price_precision)

    def round_quantity(self, qty: float, *, mode: str = "down") -> float:
        if self.quantity_step <= 0:
            return qty
        steps = qty / self.quantity_step
        if mode == "nearest":
            n = round(steps)
        else:
            n = int(steps)  # floor
        out = n * self.quantity_step
        return round(out, self.quantity_precision)


class InstrumentListResponse(BaseModel):
    default_instrument: str
    instruments: List[InstrumentSpec]
