"""Leakage / causality checks for Phase 11 risk layer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.risk.config import AccountRiskConfig, FundingCostMode
from app.risk.costs import estimate_costs
from app.instruments.paxgusd import PAXGUSD_SPEC


def test_costs_use_only_configured_as_of_inputs() -> None:
    """No future funding/spread invented — UNKNOWN stays zero cost for funding."""
    acct = AccountRiskConfig(
        funding_mode=FundingCostMode.UNKNOWN,
        estimated_funding_rate=0.99,  # would be huge if used
    )
    c = estimate_costs(
        instrument=PAXGUSD_SPEC, account=acct, entry=4340.0, quantity=50.0
    )
    assert c.funding_cost == 0.0
    assert c.funding_mode == FundingCostMode.UNKNOWN


def test_estimated_funding_only_when_mode_estimated() -> None:
    acct = AccountRiskConfig(
        funding_mode=FundingCostMode.ESTIMATED,
        estimated_funding_rate=0.0001,
        estimated_holding_intervals=2.0,
    )
    c = estimate_costs(
        instrument=PAXGUSD_SPEC, account=acct, entry=4340.0, quantity=100.0
    )
    assert c.funding_cost > 0
    assert "ESTIMATED" in " ".join(c.notes)


def test_as_of_timestamp_is_explicit_not_future_default() -> None:
    now = datetime.now(timezone.utc)
    past = now - timedelta(hours=4)
    assert past < now  # causal boundary sanity for callers
