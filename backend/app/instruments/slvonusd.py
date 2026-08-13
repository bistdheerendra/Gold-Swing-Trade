"""SLVONUSD instrument — Delta Exchange India (verified via public products API)."""

from __future__ import annotations

from app.instruments.schemas import InstrumentSpec, InstrumentType, SpecVerification

# Source: GET https://api.india.delta.exchange/v2/products (perpetual_futures)
# Verified Phase 11.12 — live product row for symbol SLVONUSD
# (iShares Silver Trust / Ondo tokenized silver).
SLVONUSD_SPEC = InstrumentSpec(
    symbol="SLVONUSD",
    base_asset="SLVON",
    quote_asset="USD",
    instrument_type=InstrumentType.PERPETUAL,
    contract_size=0.1,  # Delta API: contract_value "0.1" SLVON per contract
    quantity_step=1.0,  # integer contracts (same assumption as PAXGUSD)
    minimum_quantity=1.0,
    maximum_quantity=62_000.0,  # Delta API: position_size_limit
    tick_size=0.01,  # Delta API
    price_precision=2,
    quantity_precision=0,
    margin_currency="USD",
    leverage_limits=[1.0, 3.0, 5.0, 10.0, 20.0, 50.0],  # ui_config.leverage_slider_values
    max_leverage=50.0,  # API default_leverage + UI max
    default_research_leverage=5.0,  # NEVER default to exchange max
    maker_fee=0.0001,  # Delta API 0.01%
    taker_fee=0.0001,
    funding_supported=True,
    funding_interval_seconds=28800,  # product_specs.rate_exchange_interval (8h)
    trading_hours="24/7",
    data_source="https://api.india.delta.exchange/v2/products",
    verification=SpecVerification.VERIFIED_API,
    verification_notes=[
        "contract_value=0.1, tick_size, fees, position_size_limit=62000, funding 8h from Delta India products API",
        "description: iShares Silver (XAG) Trust ONDO Token perpetual future quoted in USD",
        "quantity_step=1 assumed (integer contracts) — confirm on exchange UI before live use",
        "Independent research track from PAXGUSD — do not blend stats or inherit Phase 12 gate",
        "INR-settled account UX uses configurable USD/INR conversion for risk amounts",
    ],
    exchange="DELTA_EXCHANGE_INDIA",
)
