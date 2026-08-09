# Position Sizing — Phase 11

## Formula (PAXGUSD)

Delta India `contract_value` = **0.001 PAXG per contract**.

For stop distance \(D\) (price units):

\[
\text{loss per contract (USD)} = 0.001 \times D
\]

\[
Q_{raw} = \frac{\text{risk USD}}{0.001 \times D}
\]

Then round **down** to `quantity_step` (1 contract), clamp to min/max.

## Examples (USD/INR = 83 CONFIGURED)

### ₹30,000 · 1% risk · SL $10 · entry $4340

- Risk = ₹300 ≈ **$3.614**
- Loss/contract = 0.001 × 10 = **$0.01**
- Raw qty ≈ **361** → quantity **361**
- Notional ≈ 361 × 0.001 × 4340 ≈ **$1,566**
- Margin @ 5x ≈ **$313** ≈ ₹26,000 (check buffer)

### ₹10,000 · 1% risk · same SL

- Risk ≈ **$1.205** → raw qty ≈ **120**

### Risk 0.5% / 1% / 2%

Scale quantity roughly linearly with risk % (before min/max clamps).

## Do not

- Size as `balance × leverage`
- Auto-raise leverage when margin fails — **reduce quantity**
