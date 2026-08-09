"""Technical analysis package — Phase 3.

All indicators are causal: value at index i uses only bars[0..i].
Swing pivots are emitted only after right-side confirmation (no look-ahead features).
"""
