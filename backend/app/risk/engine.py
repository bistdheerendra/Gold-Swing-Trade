"""RiskEngine — sizes/validates Phase 10 signals; never invents BUY/SELL."""

from __future__ import annotations

from typing import List, Optional, Sequence

from app.combined.schemas import CombinedSignalResult
from app.instruments.registry import DEFAULT_INSTRUMENT, get_instrument
from app.instruments.validation import validate_stop_loss, validate_targets
from app.risk.config import AccountRiskConfig
from app.risk.costs import estimate_costs
from app.risk.guards import DailyRiskState, check_daily_and_streak
from app.risk.margin import check_margin
from app.risk.schemas import RiskStatus, TargetRiskRow, TradePlan
from app.risk.sizing import size_position
from app.strategy.schemas import SignalDirection, StrategyAnalyzeResult, TakeProfitLevel


class RiskEngine:
    def __init__(self, account: Optional[AccountRiskConfig] = None) -> None:
        self.account = account or AccountRiskConfig()

    def plan_from_combined(
        self,
        signal: CombinedSignalResult,
        *,
        account: Optional[AccountRiskConfig] = None,
        leverage: Optional[float] = None,
        daily: Optional[DailyRiskState] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
    ) -> TradePlan:
        acct = account or self.account
        return self.build_plan(
            symbol=signal.symbol or DEFAULT_INSTRUMENT,
            direction=signal.direction,
            entry=signal.entry.preferred if signal.entry else None,
            stop_loss=signal.stop_loss,
            targets=signal.targets,
            rule_score=signal.rule_score,
            ml_prediction=signal.ml_prediction,
            ml_confidence=signal.ml_confidence,
            account=acct,
            leverage=leverage,
            daily=daily,
            bid=bid,
            ask=ask,
            signal_notes=list(signal.notes),
        )

    def plan_from_strategy(
        self,
        result: StrategyAnalyzeResult,
        *,
        symbol: str = DEFAULT_INSTRUMENT,
        account: Optional[AccountRiskConfig] = None,
        leverage: Optional[float] = None,
        daily: Optional[DailyRiskState] = None,
    ) -> TradePlan:
        acct = account or self.account
        return self.build_plan(
            symbol=symbol,
            direction=result.signal,
            entry=result.entry.preferred if result.entry else None,
            stop_loss=result.stop_loss,
            targets=result.targets,
            rule_score=result.score,
            account=acct,
            leverage=leverage,
            daily=daily,
        )

    def build_plan(
        self,
        *,
        symbol: str,
        direction: SignalDirection,
        entry: Optional[float],
        stop_loss: Optional[float],
        targets: Sequence[TakeProfitLevel],
        account: AccountRiskConfig,
        leverage: Optional[float] = None,
        daily: Optional[DailyRiskState] = None,
        rule_score: Optional[int] = None,
        ml_prediction: Optional[str] = None,
        ml_confidence: Optional[float] = None,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        signal_notes: Optional[List[str]] = None,
    ) -> TradePlan:
        instr = get_instrument(symbol)
        lev = leverage if leverage is not None else account.default_leverage
        notes = list(signal_notes or []) + [
            "Phase 11 sizes Phase 10 signals only — never invents trades",
            "RESEARCH ONLY — no broker orders",
        ]
        reasons: List[str] = []
        risks: List[str] = []

        base = TradePlan(
            instrument=instr.symbol,
            direction=direction,
            signal_status=direction.value,
            rule_score=rule_score,
            ml_prediction=ml_prediction,
            ml_confidence=ml_confidence,
            entry=entry,
            stop_loss=stop_loss,
            targets=list(targets),
            account_balance=account.account_balance,
            currency=account.currency,
            risk_percent=account.risk_per_trade_pct,
            risk_amount=account.risk_amount_account(),
            risk_amount_usd=account.risk_amount_usd(),
            leverage=lev,
            instrument_spec=instr,
            account=account,
            notes=notes,
        )

        # WAIT / NO_TRADE — never size
        if direction in (SignalDirection.WAIT, SignalDirection.NO_TRADE):
            base.risk_status = RiskStatus.SKIPPED_NO_SIGNAL
            base.reasons = ["No trade setup — risk engine does not create BUY/SELL"]
            return base

        guard = check_daily_and_streak(
            account,
            daily
            or DailyRiskState(starting_daily_equity=account.account_balance),
        )
        if not guard.ok:
            base.risk_status = RiskStatus(guard.status)
            base.reasons = guard.reasons
            return base

        if entry is None or stop_loss is None:
            base.risk_status = RiskStatus.INVALID
            base.reasons = ["Missing entry or stop_loss"]
            return base

        entry_r = instr.round_price(float(entry))
        sl_r = instr.round_price(float(stop_loss))
        base.entry = entry_r
        base.stop_loss = sl_r

        slv = validate_stop_loss(
            direction=direction,
            entry=entry_r,
            stop_loss=sl_r,
            instrument=instr,
            min_stop_distance=instr.tick_size * account.min_stop_ticks,
            max_stop_distance_pct=account.max_stop_distance_pct,
        )
        if not slv.ok:
            base.risk_status = RiskStatus.INVALID
            base.reasons = slv.reasons
            return base
        base.stop_distance = slv.stop_distance
        base.stop_distance_pct = slv.stop_distance_pct
        reasons.extend(slv.reasons)

        tv = validate_targets(direction=direction, entry=entry_r, targets=list(targets))
        if not tv.ok:
            base.risk_status = RiskStatus.INVALID
            base.reasons = tv.reasons
            return base

        sized = size_position(
            instrument=instr,
            account=account,
            entry=entry_r,
            stop_distance=float(slv.stop_distance or 0),
        )
        if not sized.ok:
            base.risk_status = RiskStatus.RISK_REJECTED
            base.reasons = sized.reasons
            base.raw_quantity = sized.raw_quantity
            return base

        base.raw_quantity = sized.raw_quantity
        base.quantity = sized.rounded_quantity
        base.notional_value = sized.notional_usd
        reasons.extend(sized.reasons)

        margin = check_margin(
            instrument=instr,
            account=account,
            notional_usd=sized.notional_usd,
            leverage=lev,
        )
        base.required_margin_usd = margin.required_margin_usd
        base.required_margin = margin.required_margin_account
        if not margin.ok:
            if not margin.exposure_ok:
                base.risk_status = RiskStatus.POSITION_LIMIT_EXCEEDED
            else:
                base.risk_status = RiskStatus.INSUFFICIENT_MARGIN
            base.reasons = margin.reasons
            return base

        costs = estimate_costs(
            instrument=instr,
            account=account,
            entry=entry_r,
            quantity=sized.rounded_quantity,
            bid=bid,
            ask=ask,
        )
        base.costs = costs
        base.spread_cost = costs.spread_cost
        base.slippage_cost = costs.slippage_cost
        base.trading_fee = costs.trading_fee
        base.funding_cost = costs.funding_cost
        base.estimated_total_cost = costs.estimated_total_cost
        base.cost_currency = costs.currency
        notes.extend(costs.notes)
        if costs.spread_source.value == "UNKNOWN" and account.spread_source.value == "UNKNOWN":
            # still allow plan but flag
            risks.append("COST_DATA_UNAVAILABLE for spread — treated carefully")

        # Gross risk ≈ risk_usd; net risk adds costs (USD)
        gross_risk = sized.risk_amount_usd
        net_risk = gross_risk + costs.estimated_total_cost
        target_rows: List[TargetRiskRow] = []
        for t in targets:
            if direction == SignalDirection.BUY:
                gross_rew = sized.rounded_quantity * instr.contract_size * (t.price - entry_r)
            else:
                gross_rew = sized.rounded_quantity * instr.contract_size * (entry_r - t.price)
            net_rew = gross_rew - costs.estimated_total_cost
            g_rr = gross_rew / gross_risk if gross_risk > 0 else 0.0
            n_rr = net_rew / net_risk if net_risk > 0 else 0.0
            target_rows.append(
                TargetRiskRow(
                    label=t.label,
                    price=t.price,
                    gross_reward_usd=round(gross_rew, 4),
                    net_reward_usd=round(net_rew, 4),
                    gross_rr=round(g_rr, 4),
                    net_rr=round(n_rr, 4),
                )
            )
        base.target_rows = target_rows
        if target_rows:
            base.gross_rr = target_rows[0].gross_rr
            base.net_rr = target_rows[0].net_rr

        if base.net_rr is not None and base.net_rr < account.minimum_rr:
            base.risk_status = RiskStatus.RISK_REJECTED
            base.reasons = [
                f"net_RR {base.net_rr:.2f} < minimum_rr {account.minimum_rr}"
            ]
            base.risks = risks
            base.notes = notes
            return base

        base.risk_status = RiskStatus.RISK_ACCEPTED
        base.reasons = reasons + [
            f"Risk {account.risk_per_trade_pct}% = {account.risk_amount_account():.2f} "
            f"{account.currency}",
            f"Qty {base.quantity} contracts · notional ${base.notional_value:.2f}",
            f"Margin {base.required_margin:.2f} {account.currency} @ {lev}x",
            f"Net RR (TP1) {base.net_rr}",
        ]
        base.risks = risks
        base.notes = notes
        return base
