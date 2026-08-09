"""Instrument registry."""

from __future__ import annotations

from typing import Dict, List

from app.instruments.paxgusd import PAXGUSD_SPEC
from app.instruments.schemas import InstrumentSpec, InstrumentType, SpecVerification

DEFAULT_INSTRUMENT = "PAXGUSD"

# Spot gold research pair (not Delta perpetual) — configurable, not exchange-verified
XAUUSD_SPEC = InstrumentSpec(
    symbol="XAUUSD",
    base_asset="XAU",
    quote_asset="USD",
    instrument_type=InstrumentType.SPOT,
    contract_size=1.0,  # 1 unit = 1 oz notionally for research
    quantity_step=0.01,
    minimum_quantity=0.01,
    maximum_quantity=100.0,
    tick_size=0.01,
    price_precision=2,
    quantity_precision=2,
    margin_currency="USD",
    max_leverage=1.0,
    default_research_leverage=1.0,
    maker_fee=0.0,
    taker_fee=0.0,
    funding_supported=False,
    funding_interval_seconds=None,
    trading_hours="varies",
    data_source="research_config",
    verification=SpecVerification.CONFIGURED,
    verification_notes=[
        "Spot-style research instrument — not Delta PAXGUSD perpetual",
        "contract_size=1 oz research assumption — UNVERIFIED for any broker",
    ],
    exchange="RESEARCH",
)

_REGISTRY: Dict[str, InstrumentSpec] = {
    PAXGUSD_SPEC.symbol: PAXGUSD_SPEC,
    XAUUSD_SPEC.symbol: XAUUSD_SPEC,
}


def get_instrument(symbol: str) -> InstrumentSpec:
    key = symbol.strip().upper()
    if key not in _REGISTRY:
        raise ValueError(f"Unknown instrument: {symbol}. Known: {list(_REGISTRY)}")
    return _REGISTRY[key]


def list_instruments() -> List[InstrumentSpec]:
    return list(_REGISTRY.values())


def register_instrument(spec: InstrumentSpec) -> None:
    _REGISTRY[spec.symbol.upper()] = spec
