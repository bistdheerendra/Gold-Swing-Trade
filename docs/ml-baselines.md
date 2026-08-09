# ML Baselines (Phase 9)

ML must beat (or clearly fail against) simple baselines on **validation**:

1. **Majority class** — always predict the TRAIN majority label  
2. **Random classifier** — sample TRAIN label distribution  
3. **Phase 6 strategy outcome distribution** — class mix from rule labels  
4. **Strategy score threshold** — e.g. `strategy_score >= 65` heuristic  

## Rule vs ML comparison

For `strategy_outcome` research:

- Phase 6 rule trades alone (using `future_R`)
- ML filter on rule setups: accept when P(WIN) ≥ threshold
- Thresholds `{0.50 … 0.75}` scanned on **VALIDATION**; selected threshold applied once to TEST

Combination tags (research): `RULE_BUY_ML_ACCEPT`, `RULE_BUY_ML_REJECT`, `RULE_SELL_ML_*`, `WAIT`, `NO_TRADE`.

Do not assume ML improves expectancy. Report both sides.
