# PAXGUSD Instrument — Phase 11

## Source

Public Delta Exchange India products API:

`GET https://api.india.delta.exchange/v2/products`

Verification: `SpecVerification.VERIFIED_API` for fields pulled from the product row.

## Spec (research defaults)

| Field | Value | Notes |
|-------|-------|-------|
| symbol | PAXGUSD | Default instrument |
| type | PERPETUAL | |
| contract_size | 0.001 | API `contract_value` |
| tick_size | 0.01 | API |
| quantity_step | 1 | Assumed integer contracts — confirm on UI |
| min qty | 1 | |
| max qty | 200000 | API `position_size_limit` |
| maker/taker fee | 0.0001 (0.01%) | API — fees change; config overrides |
| funding interval | 14400 s (4h) | API |
| max leverage (research cap) | 50 | Community/product guide |
| default research leverage | **5** | Never default to exchange max |

## Unverified / configured

- `quantity_step=1` — mark as assumed
- `usd_inr_rate` for INR account UX — CONFIGURED
- Live bid/ask / live funding — **UNKNOWN** until a read-only feed exists

## Extensibility

Register additional instruments in `instruments/registry.py` without changing `RiskEngine`.
