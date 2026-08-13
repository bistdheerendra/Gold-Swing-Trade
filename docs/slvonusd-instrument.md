# SLVONUSD Instrument — Phase 11.12

Delta Exchange India perpetual for **iShares Silver (XAG) Trust ONDO Token**, quoted in USD.

## Spec (verified via `GET /v2/products`)

| Field | Value |
|-------|-------|
| symbol | SLVONUSD |
| contract_value | 0.1 SLVON / contract |
| tick_size | 0.01 |
| maker / taker | 0.01% |
| position_size_limit | 62 000 |
| funding interval | 8h |
| research default leverage | 5× (never exchange max) |

Source of truth in code: `backend/app/instruments/slvonusd.py`.

## Independence

- Separate OHLCV files: `data/historical/SLVONUSD_*.csv`
- Separate risk instrument entry — **not** PAXGUSD’s contract size or funding
- Own Phase 12 gate (not yet evaluated); does not inherit or clear PAXGUSD’s NO-GO

See also: [market-data.md](market-data.md), [theming.md](theming.md), [paxgusd-instrument.md](paxgusd-instrument.md).
