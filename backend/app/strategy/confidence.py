"""Map condition scores to signal thresholds (not probabilities)."""

from __future__ import annotations

from app.strategy.config import StrategyConfig
from app.strategy.schemas import SignalDirection


def score_band(score: int, config: StrategyConfig) -> str:
    if score >= config.strong_signal_threshold:
        return "STRONG"
    if score >= config.signal_threshold:
        return "VALID"
    if score >= config.wait_threshold:
        return "WAIT_BAND"
    return "NO_TRADE_BAND"


def direction_from_scores(
    *,
    buy_score: int,
    sell_score: int,
    config: StrategyConfig,
    buy_hard_block: bool,
    sell_hard_block: bool,
    buy_conflict: bool,
    sell_conflict: bool,
) -> tuple[SignalDirection, int, str]:
    """
    Choose BUY/SELL/WAIT/NO_TRADE from directional scores.

    Hard blocks (validation / extreme vol / unsafe) → NO_TRADE for that side.
    Strong conflicts → NO_TRADE for that side.
    """
    buy_eff = -1 if buy_hard_block or buy_conflict else buy_score
    sell_eff = -1 if sell_hard_block or sell_conflict else sell_score

    # Prefer the stronger eligible side at/above signal threshold
    candidates: list[tuple[SignalDirection, int]] = []
    if buy_eff >= config.signal_threshold:
        candidates.append((SignalDirection.BUY, buy_eff))
    if sell_eff >= config.signal_threshold:
        candidates.append((SignalDirection.SELL, sell_eff))

    if candidates:
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_dir, best_score = candidates[0]
        # Ambiguous: both sides valid and close
        if len(candidates) == 2 and abs(candidates[0][1] - candidates[1][1]) < 5:
            return (
                SignalDirection.NO_TRADE,
                max(buy_score, sell_score),
                "Ambiguous BUY and SELL scores — NO_TRADE",
            )
        return best_dir, best_score, f"{best_dir.value} score {best_score}/100"

    # High score blocked by validation/filters/conflict → NO_TRADE (not WAIT)
    if buy_score >= config.signal_threshold and (buy_hard_block or buy_conflict):
        return (
            SignalDirection.NO_TRADE,
            buy_score,
            "BUY setup blocked by validation/conflict",
        )
    if sell_score >= config.signal_threshold and (sell_hard_block or sell_conflict):
        return (
            SignalDirection.NO_TRADE,
            sell_score,
            "SELL setup blocked by validation/conflict",
        )

    # WAIT band
    wait_buy = (not buy_hard_block and not buy_conflict) and (
        config.wait_threshold <= buy_score < config.signal_threshold
    )
    wait_sell = (not sell_hard_block and not sell_conflict) and (
        config.wait_threshold <= sell_score < config.signal_threshold
    )
    if wait_buy or wait_sell:
        best = max(
            buy_score if wait_buy else -1,
            sell_score if wait_sell else -1,
        )
        return SignalDirection.WAIT, best, "Setup forming — waiting for confirmation"

    # Soft incomplete near wait band
    soft = max(buy_score, sell_score)
    if soft >= config.wait_threshold and not (buy_hard_block or sell_hard_block or buy_conflict or sell_conflict):
        return SignalDirection.WAIT, soft, "Incomplete confirmation"

    reason = "Below wait threshold"
    if buy_conflict or sell_conflict:
        reason = "Structural conflict"
    if buy_hard_block or sell_hard_block:
        reason = "Trade validation / filters failed"
    return SignalDirection.NO_TRADE, soft, reason
