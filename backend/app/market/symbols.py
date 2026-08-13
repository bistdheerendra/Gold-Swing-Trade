"""Supported research symbols (decision-support — not live broker pairs)."""

from __future__ import annotations

import os
from typing import Dict, List

from pydantic import BaseModel, Field

# Anchor mock OHLCV near live spot (~4340 as of 2026). Not a live feed.
# Override: MOCK_GOLD_BASE_PRICE=4341.935
_DEFAULT_GOLD = float(os.getenv("MOCK_GOLD_BASE_PRICE", "4340.0"))
# SLVONUSD mock anchor near live Delta mark (~58.7 as of Phase 11.12 verify)
_DEFAULT_SILVER = float(os.getenv("MOCK_SILVER_BASE_PRICE", "58.7"))


class SymbolInfo(BaseModel):
    symbol: str
    label: str
    asset_class: str = "precious_metals"
    description: str = ""
    mock_base_price: float = 4340.0
    quote: str = "USD"


SUPPORTED_SYMBOLS: Dict[str, SymbolInfo] = {
    "PAXGUSD": SymbolInfo(
        symbol="PAXGUSD",
        label="PAX Gold / PAXGUSD",
        description=(
            "PAX Gold perpetual on Delta Exchange India — authoritative "
            "public candles (verified via /v2/products)"
        ),
        mock_base_price=round(_DEFAULT_GOLD - 2.0, 3),
    ),
    "SLVONUSD": SymbolInfo(
        symbol="SLVONUSD",
        label="iShares Silver / SLVONUSD",
        description=(
            "Ondo tokenized silver (iShares Silver Trust) perpetual on Delta "
            "Exchange India — independent research track from PAXGUSD "
            "(verified via /v2/products)"
        ),
        mock_base_price=_DEFAULT_SILVER,
    ),
    # Legacy mock/test + optional Twelve Data reference — not in primary UI tabs
    "XAUUSD": SymbolInfo(
        symbol="XAUUSD",
        label="Gold / XAUUSD",
        description=(
            "Legacy spot gold research reference — Twelve Data XAU/USD when "
            "MARKET_DATA_PROVIDER=twelvedata (UI tab removed in Phase 11.12)"
        ),
        mock_base_price=_DEFAULT_GOLD,
    ),
}

# Primary dashboard instruments (UI + health)
PRIMARY_SYMBOLS = ("PAXGUSD", "SLVONUSD")

DEFAULT_SYMBOL = "PAXGUSD"


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def is_supported(symbol: str) -> bool:
    return normalize_symbol(symbol) in SUPPORTED_SYMBOLS


def get_symbol_info(symbol: str) -> SymbolInfo:
    key = normalize_symbol(symbol)
    if key not in SUPPORTED_SYMBOLS:
        raise ValueError(
            f"Unsupported symbol '{symbol}'. Allowed: {', '.join(SUPPORTED_SYMBOLS)}"
        )
    return SUPPORTED_SYMBOLS[key]


def list_symbols() -> List[SymbolInfo]:
    return list(SUPPORTED_SYMBOLS.values())


def list_primary_symbols() -> List[SymbolInfo]:
    return [SUPPORTED_SYMBOLS[s] for s in PRIMARY_SYMBOLS if s in SUPPORTED_SYMBOLS]


def mock_base_price(symbol: str) -> float:
    try:
        return get_symbol_info(symbol).mock_base_price
    except ValueError:
        return _DEFAULT_GOLD


class SymbolListResponse(BaseModel):
    default_symbol: str = DEFAULT_SYMBOL
    symbols: List[SymbolInfo] = Field(default_factory=list)
    note: str = (
        "Authoritative PAXGUSD + SLVONUSD OHLCV from Delta Exchange India "
        "(MARKET_DATA_PROVIDER=delta_india, no API key). "
        "Instruments are independent research tracks — do not blend series. "
        "Optional legacy XAUUSD via twelvedata. "
        "Mock only with ALLOW_MOCK_DATA=true for pytest. Not live order execution."
    )
