"""Read-only broker abstraction — Delta live ticker; no order placement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.instruments.registry import get_instrument
from app.instruments.schemas import InstrumentSpec
from app.market.delta_provider import DeltaIndiaMarketDataProvider


class BrokerAdapter(ABC):
    """READ-ONLY broker surface — no place_order / cancel_order."""

    name: str = "abstract"

    @abstractmethod
    async def get_instrument(self, symbol: str) -> InstrumentSpec:
        ...

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def get_account(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    async def get_positions(self) -> list:
        ...

    @abstractmethod
    async def get_orders(self) -> list:
        ...


class MockBrokerAdapter(BrokerAdapter):
    """Offline stub for tests when MARKET_DATA_PROVIDER=mock."""

    name = "mock_research"

    def __init__(self, *, account_balance: float = 30_000.0, currency: str = "INR") -> None:
        self.account_balance = account_balance
        self.currency = currency

    async def get_instrument(self, symbol: str) -> InstrumentSpec:
        return get_instrument(symbol)

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        return {
            "symbol": symbol.upper(),
            "bid": None,
            "ask": None,
            "last": None,
            "spread_source": "UNKNOWN",
            "note": "Mock ticker — not live Delta feed",
        }

    async def get_account(self) -> Dict[str, Any]:
        return {
            "balance": self.account_balance,
            "currency": self.currency,
            "note": "Mock account — no API keys",
        }

    async def get_positions(self) -> list:
        return []

    async def get_orders(self) -> list:
        return []


class DeltaReadOnlyBrokerAdapter(BrokerAdapter):
    """Live Delta India ticker — research only, no orders / no API keys."""

    name = "delta_india_readonly"

    def __init__(
        self,
        *,
        account_balance: float = 30_000.0,
        currency: str = "INR",
        base_url: Optional[str] = None,
    ) -> None:
        self.account_balance = account_balance
        self.currency = currency
        settings = get_settings()
        self._market = DeltaIndiaMarketDataProvider(
            base_url=base_url
            or settings.delta_india_base_url
            or settings.delta_api_base_url
        )

    async def get_instrument(self, symbol: str) -> InstrumentSpec:
        return get_instrument(symbol)

    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        return await self._market.get_ticker(symbol)

    async def get_account(self) -> Dict[str, Any]:
        return {
            "balance": self.account_balance,
            "currency": self.currency,
            "note": "Research account config only — not Delta wallet (no API keys)",
        }

    async def get_positions(self) -> list:
        return []

    async def get_orders(self) -> list:
        return []


def get_broker_adapter(
    *,
    account_balance: float = 30_000.0,
    currency: str = "INR",
) -> BrokerAdapter:
    settings = get_settings()
    settings = get_settings()
    provider = settings.market_data_provider.lower().strip().replace("-", "_")
    if provider in ("delta", "delta_india"):
        return DeltaReadOnlyBrokerAdapter(
            account_balance=account_balance, currency=currency
        )
    if provider == "mock" and settings.allow_mock_data:
        return MockBrokerAdapter(account_balance=account_balance, currency=currency)
    return MockBrokerAdapter(account_balance=account_balance, currency=currency)


class PaxgusdDataAdapter:
    """Symbol / precision mapping for PAXGUSD research (legacy name)."""

    symbol = "PAXGUSD"

    def __init__(self) -> None:
        self.spec = get_instrument("PAXGUSD")

    def normalize_symbol(self, symbol: str) -> str:
        s = symbol.strip().upper().replace("/", "").replace("-", "")
        if s in ("PAXG", "PAXGUSDT"):
            return "PAXGUSD"
        if s in ("SLV", "SLVON", "SLVONUSDT"):
            return "SLVONUSD"
        return s

    def round_price(self, price: float) -> float:
        return self.spec.round_price(price)

    def round_quantity(self, qty: float) -> float:
        return self.spec.round_quantity(qty)


class InstrumentDataAdapter:
    """Per-symbol precision mapping for Delta research instruments."""

    def __init__(self, symbol: str = "PAXGUSD") -> None:
        self.symbol = symbol.strip().upper()
        self.spec = get_instrument(self.symbol)

    def normalize_symbol(self, symbol: str) -> str:
        s = symbol.strip().upper().replace("/", "").replace("-", "")
        if s in ("PAXG", "PAXGUSDT"):
            return "PAXGUSD"
        if s in ("SLV", "SLVON", "SLVONUSDT"):
            return "SLVONUSD"
        return s

    def round_price(self, price: float) -> float:
        return self.spec.round_price(price)

    def round_quantity(self, qty: float) -> float:
        return self.spec.round_quantity(qty)
