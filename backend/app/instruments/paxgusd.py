"""PAXGUSD instrument — Delta Exchange India (verified via public products API)."""

from __future__ import annotations

from app.instruments.schemas import InstrumentSpec, InstrumentType, SpecVerification

# Source: GET https://api.india.delta.exchange/v2/products (perpetual_futures)
# Fetched during Phase 11 implementation — live product row for symbol PAXGUSD.
# Community marketing also cites up to 50x leverage and 0.01% fees.
PAXGUSD_SPEC = InstrumentSpec(
    symbol="PAXGUSD",
    base_asset="PAXG",
    quote_asset="USD",
    instrument_type=InstrumentType.PERPETUAL,
    contract_size=0.001,  # Delta API: contract_value "0.001" PAXG per contract
    quantity_step=1.0,  # contracts are whole units (UNVERIFIED step; API size limit implies integer)
    minimum_quantity=1.0,
    maximum_quantity=200_000.0,  # Delta API: position_size_limit
    tick_size=0.01,  # Delta API
    price_precision=2,
    quantity_precision=0,
    margin_currency="USD",
    max_leverage=50.0,  # Community/product guide; API default_leverage field was 100 — research cap 50
    default_research_leverage=5.0,  # NEVER default to exchange max
    maker_fee=0.0001,  # Delta API 0.01%
    taker_fee=0.0001,
    funding_supported=True,
    funding_interval_seconds=14400,  # product_specs.rate_exchange_interval
    trading_hours="24/7",
    data_source="https://api.india.delta.exchange/v2/products",
    verification=SpecVerification.VERIFIED_API,
    verification_notes=[
        "contract_value, tick_size, fees, position_size_limit, funding interval from Delta India products API",
        "quantity_step=1 assumed (integer contracts) — confirm on exchange UI before live use",
        "max_leverage research default 50 (community); do not use exchange max for sizing",
        "INR-settled account UX uses configurable USD/INR conversion for risk amounts",
    ],
    exchange="DELTA_EXCHANGE_INDIA",
)
