"""Generate human-readable reasons and risks from evaluated conditions."""

from __future__ import annotations

from typing import List, Optional, Sequence

from app.strategy.schemas import (
    ConditionScore,
    SignalDirection,
    VolatilityBand,
)


def build_reasons(
    direction: SignalDirection,
    conditions: Sequence[ConditionScore],
    *,
    primary_rr: Optional[float] = None,
) -> List[str]:
    reasons: List[str] = []
    if direction in (SignalDirection.BUY, SignalDirection.SELL):
        for c in conditions:
            if c.met and c.points > 0:
                reasons.append(f"✓ {c.label}: {c.detail}" if c.detail else f"✓ {c.label}")
        if primary_rr is not None:
            reasons.append(f"✓ RR = 1:{primary_rr:.2f}")
    elif direction == SignalDirection.WAIT:
        missing = [c for c in conditions if not c.met]
        if missing:
            # Highlight the most important missing pieces
            for c in missing[:4]:
                reasons.append(f"⏳ Waiting: {c.label} — {c.detail or 'incomplete'}")
        else:
            reasons.append("⏳ Setup near threshold — waiting for stronger confirmation")
    else:
        failed = [c for c in conditions if not c.met]
        for c in failed[:5]:
            reasons.append(f"✗ {c.label}: {c.detail or 'not met'}")
        if not reasons:
            reasons.append("✗ No valid trade setup")
    return reasons


def build_risks(
    *,
    volatility: VolatilityBand,
    conditions: Sequence[ConditionScore],
    primary_rr: Optional[float],
    min_rr: float,
    extra: Optional[Sequence[str]] = None,
) -> List[str]:
    risks: List[str] = []
    if volatility == VolatilityBand.HIGH:
        risks.append("⚠ Elevated ATR (high volatility)")
    elif volatility == VolatilityBand.EXTREME:
        risks.append("⚠ Extreme ATR — trade filtered")
    elif volatility == VolatilityBand.UNKNOWN:
        risks.append("⚠ Volatility unclassified")

    loc = next((c for c in conditions if c.key == "premium_discount"), None)
    if loc and not loc.met:
        risks.append(f"⚠ Location: {loc.detail}")

    entry = next((c for c in conditions if c.key == "entry_15m"), None)
    if entry and not entry.met:
        risks.append("⚠ Entry timeframe confirmation incomplete")

    if primary_rr is not None and primary_rr < min_rr:
        risks.append(f"⚠ RR {primary_rr:.2f} below minimum {min_rr}")

    if extra:
        for e in extra:
            if e and e not in risks:
                risks.append(e if e.startswith("⚠") else f"⚠ {e}")
    return risks
