# Cost Model — Phase 11

## Components

| Cost | How |
|------|-----|
| Spread | LIVE bid/ask, else CONFIGURED `estimated_spread`, else UNKNOWN (not pretended as zero in narrative) |
| Slippage | `slippage_pct` both sides |
| Fees | maker/taker from InstrumentSpec × 2 (entry+exit); overrideable |
| Funding | ZERO / ESTIMATED / ACTUAL / **UNKNOWN** |

## Funding

PAXGUSD is perpetual. When `funding_mode=UNKNOWN`, **funding_cost = 0** and notes state UNKNOWN — we do **not** invent rates.

## Gross vs net RR

- Gross reward from entry→TP geometry × size
- Net reward subtracts `estimated_total_cost`
- `net_RR` used for `minimum_rr` filter (default 1.5)

## Fees are not permanent

Update InstrumentSpec / AccountRiskConfig without code changes to fee logic.
